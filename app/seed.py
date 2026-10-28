import random
from app.db import get_conn, init_db


def seed():
    init_db()
    rng = random.Random(42)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM products WHERE price IS NULL"
        ).fetchall()
        for r in rows:
            price = rng.choice([199, 249, 299, 349, 449, 599, 799])
            cost = round(price * rng.uniform(0.35, 0.75), 2)
            qty = rng.choice([2, 5, 8, 15, 30, 60])
            conn.execute(
                "UPDATE products SET price=?, cost=?, quantity=? WHERE id=?",
                (price, cost, qty, r["id"]),
            )
    print(f"seeded {len(rows)} products")


if __name__ == "__main__":
    seed()