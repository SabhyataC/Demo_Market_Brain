import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import get_conn
from app.audit import log
from app.model_client import ask
from app.catalog import parse_json_list
from app.budget import check_budget
from app.policy import check_variants
from pathlib import Path
from app.model_client import generate_image

router = APIRouter(prefix="/ads", tags=["ads"])

PROMPT = """Write 3 different Facebook/Instagram ad copy variants for this product.
Product: {name}
Brand: {brand}
Price: Rs {price}
Each variant must use a different angle (for example: everyday use, gifting,
treat yourself). Be warm and specific, mention the product by name.
Allowed: lifestyle and benefit language. Not allowed: health or medical claims,
guarantees, fake discounts or urgency, invented reviews, statistics, "best" or "#1".
Return ONLY a JSON array, no other text. Each item:
{{"headline": "max 40 characters", "text": "max 125 characters", "cta": "Shop Now"}}"""


class AdIn(BaseModel):
    product_id: int
    daily_budget: float = 200


@router.post("/generate")
def generate(body: AdIn):
    check_budget({"daily_budget": body.daily_budget})
    with get_conn() as conn:
        p = conn.execute(
            "SELECT id, name, brand, price FROM products WHERE id = ?",
            (body.product_id,),
        ).fetchone()
    if not p:
        raise HTTPException(404, "Product not found")

    variants = parse_json_list(
        ask(PROMPT.format(name=p["name"], brand=p["brand"] or "n/a", price=p["price"]))
    )
    variants = [v for v in variants if v.get("headline") and v.get("text")][:3]
    if not variants:
        raise HTTPException(502, "Model returned no usable ad copy, try again")
    variants = check_variants(
        variants, {"name": p["name"], "brand": p["brand"], "price": p["price"]}
    )

    Path("static/ads").mkdir(parents=True, exist_ok=True)
    image_url = None
    try:
        fname = f"ad_{p['id']}_{int(__import__('time').time())}.png"
        generate_image(
            f"Clean, bright lifestyle product photo for a social media ad: "
            f"a package of {p['name']} by {p['brand'] or 'a small brand'} on a wooden shelf, soft daylight. "
            f'The package label must clearly read "{p["name"]}"'
            + (f' and "{p["brand"]}"' if p["brand"] else "")
            + ", spelled exactly, in clean readable lettering. No other text, no people.",
        )
        image_url = f"/static/ads/{fname}"
    except Exception as e:
        log("ai", "ad_image_failed", f"product={p['id']} {str(e)[:120]}")

    payload = {
        "product_id": p["id"],
        "product_name": p["name"],
        "daily_budget": body.daily_budget,
        "variants": variants,
        "image_url": image_url,
    }
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO proposals (kind, payload) VALUES (?, ?)",
            ("ad_draft", json.dumps(payload)),
        )
        pid = cur.lastrowid
    log("ai", "ad_draft_created", f"id={pid} product={p['id']}")
    return {"proposal_id": pid, **payload}