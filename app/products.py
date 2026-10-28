from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import get_conn
from app.audit import log

router = APIRouter()


class ProductIn(BaseModel):
    name: str
    brand: str | None = None
    variant: str | None = None
    size: str | None = None
    quantity: int = 1
    price: float | None = None
    cost: float | None = None


@router.post("/products")
def add_product(p: ProductIn):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, brand, variant, size, quantity, price, cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (p.name, p.brand, p.variant, p.size, p.quantity, p.price, p.cost),
        )
        pid = cur.lastrowid
    log("owner", "product_added", f"id={pid} name={p.name}")
    return {"id": pid}


@router.get("/products")
def list_products():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@router.get("/products/{pid}")
def get_product(pid: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "Product not found")
    return dict(row)