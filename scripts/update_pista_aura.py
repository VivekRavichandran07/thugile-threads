"""Sync Pista Aura and Pista Aura - Scallop variants from the price sheet.

Safe to run more than once. Uses the same database as the app (DATABASE_PATH),
so it works locally and on Railway:

    python scripts/update_pista_aura.py            # local DB
    railway ssh -- /app/.venv/bin/python scripts/update_pista_aura.py   # live DB

Pista Aura has S through 4XL. Pista Aura - Scallop is a separate M/L/XL product.
Both use the price-sheet cost 1271, MRP 1900 and launch price 1499.
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

NAME = "Pista Aura"
SCALLOP_NAME = "Pista Aura - Scallop"
CATEGORY = "Ethnic Wear"
COLOR = "green"
IMAGE_URL = "/static/storefront/assets/Chudidar/PistaAura1.webp"
SCALLOP_IMAGE_URL = ""
COST_PRICE = 1271
SELLING_PRICE = 1900
DISCOUNTED_PRICE = 1499
VARIANTS = [
    ("S", "TTRSGES00037"), ("M", "TTRSGEM00038"), ("L", "TTRSGEL00039"),
    ("XL", "TTRSGEXL00040"), ("2XL", "TTRSGE2XL00041"),
    ("3XL", "TTRSGE3XL00042"), ("4XL", "TTRSGE4XL00043"),
]
SCALLOP_VARIANTS = [
    ("M", "TTRSGEM00034"), ("L", "TTRSGEL00035"), ("XL", "TTRSGEXL00036"),
]
QUANTITY = 1
SOLD_OUT_SKUS = {"TTRSGE4XL00043"}


def main():
    conn = get_connection()
    created_at = now_iso()
    try:
        for product_name, variants, image_url in (
            (NAME, VARIANTS, IMAGE_URL),
            (SCALLOP_NAME, SCALLOP_VARIANTS, SCALLOP_IMAGE_URL),
        ):
            for size, sku in variants:
                row = conn.execute(
                    "SELECT id, name, quantity FROM products WHERE sku = ?", (sku,)
                ).fetchone()
                if row and row["name"] not in {NAME, SCALLOP_NAME}:
                    raise RuntimeError(
                        f"SKU {sku} belongs to {row['name']}; refusing to repurpose it."
                    )
                # Keep recorded stock; restock only an empty, unsold listing.
                if row:
                    sold = conn.execute(
                        "SELECT 1 FROM sales WHERE product_id = ? LIMIT 1", (row["id"],)
                    ).fetchone()
                    quantity = 0 if sku in SOLD_OUT_SKUS else (
                        row["quantity"] if (row["quantity"] > 0 or sold) else QUANTITY
                    )
                    conn.execute(
                        """
                        UPDATE products
                        SET name = ?, category = ?, size = ?, color = ?, image_url = ?,
                            cost_price = ?, selling_price = ?, discounted_price = ?,
                            quantity = ?, is_archived = 0, created_at = ?
                        WHERE id = ?
                        """,
                        (product_name, CATEGORY, size, COLOR, image_url, COST_PRICE,
                         SELLING_PRICE, DISCOUNTED_PRICE, quantity, created_at, row["id"]),
                    )
                else:
                    quantity = 0 if sku in SOLD_OUT_SKUS else QUANTITY
                    conn.execute(
                        """
                        INSERT INTO products
                            (name, sku, category, size, color, image_url, cost_price,
                             selling_price, discounted_price, quantity, reorder_level,
                             created_at, is_archived)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """,
                        (product_name, sku, CATEGORY, size, COLOR, image_url, COST_PRICE,
                         SELLING_PRICE, DISCOUNTED_PRICE, quantity, 1, created_at),
                    )
                print(f"synced {product_name}: {sku} ({size}) qty={quantity}")
        conn.commit()
    finally:
        conn.close()
    print(f"done: {DB_PATH}")


if __name__ == "__main__":
    main()
