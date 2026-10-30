import json
from fastapi import APIRouter, HTTPException
from app.db import get_conn
from app.audit import log
from app.model_client import ask
from app.catalog import parse_json_list

router = APIRouter(prefix="/planner", tags=["planner"])
from app.calllog import purpose

PROMPT = """You are a marketing planner for a small shop.
Pick exactly 3 products to promote this week.
Prefer healthy margin and enough stock to sell. Use ONLY the numbers given.
Return ONLY a JSON array, no other text. Each item:
{{"product_id": <id>, "reason": "one sentence citing its margin % and stock, plus one specific marketing angle for this product"}}

Products:
{products}"""


@router.post("/run")
def run_planner():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.id, p.name, p.price, p.cost, COALESCE(SUM(v.stock), 0) AS quantity "
            "FROM products p LEFT JOIN variants v ON v.product_id = p.id "
            "WHERE p.price IS NOT NULL AND p.cost IS NOT NULL AND p.price > 0 "
            "GROUP BY p.id HAVING quantity > 0"
        ).fetchall()
    if len(rows) < 3:
        raise HTTPException(400, "Need at least 3 products with price, cost and stock")

    products = [
        {
            "id": r["id"], "name": r["name"], "price": r["price"],
            "margin_pct": round((r["price"] - r["cost"]) / r["price"] * 100, 1),
            "stock": r["quantity"],
        }
        for r in rows
    ]
    by_id = {p["id"]: p for p in products}

    with purpose("planner"):
        raw = ask(PROMPT.format(products=json.dumps(products)))
    picks = parse_json_list(raw)
    valid, seen = [], set()
    for pk in picks:
        pid = pk.get("product_id")
        if pid in by_id and pid not in seen:
            seen.add(pid)
            valid.append({**by_id[pid], "reason": pk.get("reason", "")})
    if len(valid) != 3:
        raise HTTPException(502, f"Model returned {len(valid)} valid picks, try again")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO proposals (kind, payload) VALUES (?, ?)",
            ("promotion", json.dumps({"picks": valid})),
        )
        pid = cur.lastrowid
    log("ai", "promotion_proposed", f"id={pid}")
    return {"proposal_id": pid, "picks": valid}