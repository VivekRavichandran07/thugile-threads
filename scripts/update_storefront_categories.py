"""Move the catalog into the Ethnic Wear and Pure Cotton storefront categories.

Uses the app's configured DATABASE_PATH, so it can run locally or in Railway:

    python scripts/update_storefront_categories.py
    /app/.venv/bin/python scripts/update_storefront_categories.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from db import DB_PATH, get_connection  # noqa: E402


def main():
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE products SET category = CASE "
            "WHEN lower(name) = 'citrus charm' THEN 'Pure Cotton' "
            "ELSE 'Ethnic Wear' END"
        )
        conn.execute(
            "UPDATE products SET image_url = ? WHERE lower(name) = 'citrus charm'",
            ("/static/storefront/assets/Chudidar/CitrusCharm1.webp",),
        )
        conn.execute(
            "UPDATE products SET quantity = 0 WHERE lower(name) = 'pista aura' "
            "AND upper(replace(size, ' ', '')) IN ('4XL', 'XXXXL')"
        )
        conn.commit()
        for row in conn.execute(
            "SELECT category, COUNT(*) AS product_count FROM products "
            "GROUP BY category ORDER BY category"
        ):
            print(f"{row['category']}: {row['product_count']} rows")
    finally:
        conn.close()
    print(f"done: {DB_PATH}")


if __name__ == "__main__":
    main()
