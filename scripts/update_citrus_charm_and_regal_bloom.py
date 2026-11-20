"""Apply the workbook prices and covers for Citrus Charm and Regal Bloom."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import DB_PATH, get_connection, now_iso  # noqa: E402
from image_assets import ASSET_PREFIX  # noqa: E402

VARIANTS = (
    ("Citrus Charm", "TTRSORM00047", "M", "Orange", "CitrusCharm", 1271, 1900, 1499),
    ("Citrus Charm", "TTRSORL00048", "L", "Orange", "CitrusCharm", 1271, 1900, 1499),
    ("Citrus Charm", "TTRSORXL00049", "XL", "Orange", "CitrusCharm", 1271, 1900, 1499),
    ("Regal Bloom", "TTSCREM00006", "M", "Red", "RegalBloom", 1400, 2100, 1680),
)


def main():
    if not Path(DB_PATH).is_file():
        raise FileNotFoundError(DB_PATH)

    conn = get_connection()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            for name, sku, size, color, stem, cost, mrp, launch_price in VARIANTS:
                cover = f"{ASSET_PREFIX}{stem}1.webp"
                existing = conn.execute(
                    "SELECT name, size FROM products WHERE sku = ?", (sku,)
                ).fetchone()
                if existing and (existing["name"].casefold(), existing["size"]) != (name.casefold(), size):
                    raise ValueError(f"SKU {sku} already belongs to {existing['name']} ({existing['size']})")
                if conn.execute(
                    "SELECT 1 FROM products WHERE name = ? COLLATE NOCASE AND size = ? AND sku != ?",
                    (name, size, sku),
                ).fetchone():
                    raise ValueError(f"{name} ({size}) already exists under a different SKU")

                conn.execute(
                    """
                    INSERT INTO products
                        (sku, name, size, color, image_url, cost_price, selling_price,
                         discounted_price, category, quantity, reorder_level, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Ethnic Wear', 1, 1, ?)
                    ON CONFLICT(sku) DO UPDATE SET
                        image_url = excluded.image_url, cost_price = excluded.cost_price,
                        selling_price = excluded.selling_price,
                        discounted_price = excluded.discounted_price
                    """,
                    (sku, name, size, color, cover, cost, mrp, launch_price, now_iso()),
                )
                conn.execute(
                    "UPDATE user_wishlists SET image_url = ? WHERE product_name = ? COLLATE NOCASE",
                    (cover, name),
                )

            for table, name_column in (("products", "name"), ("user_wishlists", "product_name")):
                conn.execute(
                    f"UPDATE {table} SET image_url = ? WHERE {name_column} = 'Karmughil' AND image_url = ?",
                    (ASSET_PREFIX + "Karmughil1.webp", ASSET_PREFIX + "CitrusCharm1.webp"),
                )

        print(f"Verified records in {DB_PATH}")
        for _, sku, *_ in VARIANTS:
            print(tuple(conn.execute(
                """
                SELECT sku, name, size, cost_price, selling_price, discounted_price,
                       quantity, is_archived, image_url FROM products WHERE sku = ?
                """,
                (sku,),
            ).fetchone()))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
