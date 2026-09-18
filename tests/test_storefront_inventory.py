import sqlite3

from db import DB_PATH, init_db


def test_storefront_seed_products_have_stock():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT COUNT(*) FROM products WHERE name = 'Sanganeri Block Print Kurta' AND quantity > 0"
    ).fetchone()
    conn.close()

    assert row[0] == 1
