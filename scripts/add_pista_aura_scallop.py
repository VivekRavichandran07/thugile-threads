"""Add (or re-list) Pista Aura - Scallop in the products table.

Safe to run more than once. Uses the same database as the app (DATABASE_PATH),
so it works locally and on Railway:

    python scripts/add_pista_aura_scallop.py            # local DB
    railway ssh -- python scripts/add_pista_aura_scallop.py   # live DB

Details come from "Inventory- Dress price sheet.xlsx" (raw silk, green,
cost 1271, MRP 1900, launch price 1520, one piece each in M, L and XL).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Use the same DATABASE_PATH as the app, which reads it from .env when present.
_env = os.path.join(ROOT, ".env")
if os.path.isfile(_env):
    with open(_env, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, sep, value = line.partition("=")
            if sep and key.strip() == "DATABASE_PATH" and not line.startswith("#"):
                value = value.strip().strip("'\"")
                os.environ.setdefault("DATABASE_PATH", value)

from db import DB_PATH, get_connection, now_iso  # noqa: E402

NAME = "Pista Aura - Scallop"
CATEGORY = "Chudidar"
COLOR = "Pista green"
IMAGE_URL = "/static/storefront/assets/Chudidar/PistaAura-Scallop1.webp"
COST_PRICE = 1271
SELLING_PRICE = 1900
DISCOUNTED_PRICE = 1520
VARIANTS = [("M", "TTRSGEM00034"), ("L", "TTRSGEL00035"), ("XL", "TTRSGEXL00036")]
QUANTITY = 1


def main():
    conn = get_connection()
    created_at = now_iso()
    try:
        for size, sku in VARIANTS:
            row = conn.execute("SELECT id, quantity FROM products WHERE sku = ?", (sku,)).fetchone()
            if row:
                # Keep any stock already recorded; restock only an empty, unsold listing.
                sold = conn.execute(
                    "SELECT 1 FROM sales WHERE product_id = ? LIMIT 1", (row["id"],)
                ).fetchone()
                quantity = row["quantity"] if (row["quantity"] > 0 or sold) else QUANTITY
                conn.execute(
                    """
                    UPDATE products
                    SET name = ?, category = ?, size = ?, color = ?, image_url = ?,
                        cost_price = ?, selling_price = ?, discounted_price = ?,
                        quantity = ?, is_archived = 0, created_at = ?
                    WHERE id = ?
                    """,
                    (NAME, CATEGORY, size, COLOR, IMAGE_URL, COST_PRICE, SELLING_PRICE,
                     DISCOUNTED_PRICE, quantity, created_at, row["id"]),
                )
                print(f"updated {sku} ({size}) qty={quantity}")
            else:
                conn.execute(
                    """
                    INSERT INTO products
                        (name, sku, category, size, color, image_url, cost_price, selling_price,
                         discounted_price, quantity, reorder_level, created_at, is_archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (NAME, sku, CATEGORY, size, COLOR, IMAGE_URL, COST_PRICE, SELLING_PRICE,
                     DISCOUNTED_PRICE, QUANTITY, 1, created_at),
                )
                print(f"added {sku} ({size}) qty={QUANTITY}")
        conn.commit()
    finally:
        conn.close()
    print(f"done: {DB_PATH}")


if __name__ == "__main__":
    main()
