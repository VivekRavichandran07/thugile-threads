import json

import db
import app as app_module
from app import app


def make_order(state="COMPLETED"):
    conn = db.get_connection()
    user = conn.execute("INSERT INTO users (name, email, password_hash, created_at, is_admin) VALUES ('Buyer', 'buyer@example.com', '', '2026-01-01', 1)").lastrowid
    product = conn.execute("INSERT INTO products (name, sku, quantity, selling_price, created_at) VALUES ('Current Name', 'order-test', 5, 999, '2026-01-01')").lastrowid
    items = [{"product_id": product, "name": "Purchased Kurta", "qty": 2, "unit_price": 75}]
    order = conn.execute("INSERT INTO orders (user_id, order_number, payment_state, items, total_amount, shipping_address_json, created_at) VALUES (?, ?, ?, ?, 150, ?, '2026-01-01')", (user, "TNT-" + "a" * 32, state, json.dumps(items), json.dumps({"name": "Shipping Customer"}))).lastrowid
    conn.commit()
    conn.close()
    return user, product, order


def test_completed_order_import_uses_snapshot_and_is_idempotent():
    user, product, order = make_order()
    app_module.synchronize_completed_order_sales()
    app_module.synchronize_completed_order_sales()
    conn = db.get_connection()
    assert tuple(conn.execute("SELECT product_id, quantity, selling_price, customer, product_name FROM sales").fetchone()) == (product, 2, 75, "Shipping Customer", "Purchased Kurta")
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
    # Recording historical sales must not silently change existing stock.
    assert conn.execute("SELECT quantity FROM products WHERE id = ?", (product,)).fetchone()[0] == 5
    conn.close()
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user
    page = client.get("/admin/sales").get_data(as_text=True)
    assert "Purchased Kurta" in page
    assert "Shipping Customer" in page
    assert "TNT-" + "a" * 32 in page


def test_pending_orders_are_not_sales():
    make_order("PENDING")
    app_module.synchronize_completed_order_sales()
    conn = db.get_connection()
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0
    conn.close()


def test_invalid_backfill_rolls_back_all_items():
    _, _, order = make_order()
    conn = db.get_connection()
    items = json.loads(conn.execute("SELECT items FROM orders").fetchone()[0])
    items.append({"product_id": 999999, "qty": 1, "unit_price": 10})
    conn.execute("UPDATE orders SET items = ? WHERE id = ?", (json.dumps(items), order))
    conn.commit()
    conn.close()
    app_module.synchronize_completed_order_sales()
    conn = db.get_connection()
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0
    conn.close()


def test_missing_product_uses_historical_snapshot():
    _, product, order = make_order()
    conn = db.get_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product,))
    conn.commit()
    conn.close()
    app_module.synchronize_completed_order_sales()
    conn = db.get_connection()
    row = conn.execute("SELECT product_id, product_name, quantity, selling_price FROM sales").fetchone()
    assert tuple(row) == (None, "Purchased Kurta", 2, 75)
    conn.close()


def test_legacy_order_without_product_id_uses_stored_price():
    _, _, order = make_order()
    conn = db.get_connection()
    conn.execute("UPDATE orders SET items = ? WHERE id = ?", (json.dumps([
        {"name": "Legacy Kurta", "qty": 2, "price": 75}
    ]), order))
    conn.commit()
    conn.close()
    app_module.synchronize_completed_order_sales()
    conn = db.get_connection()
    assert tuple(conn.execute("SELECT product_id, product_name, selling_price FROM sales").fetchone()) == (None, "Legacy Kurta", 75)
    conn.close()


def test_invalid_order_does_not_block_valid_order():
    user, _, order = make_order()
    conn = db.get_connection()
    conn.execute("INSERT INTO orders (user_id, order_number, payment_state, items, total_amount, created_at) VALUES (?, 'invalid-order', 'COMPLETED', 'invalid json', 150, '2026-01-01')", (user,))
    conn.commit()
    conn.close()
    app_module.synchronize_completed_order_sales()
    conn = db.get_connection()
    assert conn.execute("SELECT order_id FROM sales").fetchall()[0][0] == order
    assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
    conn.close()


def test_sale_survives_catalog_deletion():
    _, product, order = make_order()
    app_module.synchronize_completed_order_sales()
    conn = db.get_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product,))
    conn.commit()
    assert tuple(conn.execute("SELECT product_id, product_name FROM sales").fetchone()) == (None, "Purchased Kurta")
    conn.close()


def test_parallel_legacy_schema_migration(tmp_path):
    import os
    import sqlite3
    import subprocess
    import sys
    from pathlib import Path

    database = tmp_path / "parallel.db"
    conn = sqlite3.connect(database)
    conn.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, selling_price REAL NOT NULL, customer TEXT, date TEXT NOT NULL)")
    conn.execute("INSERT INTO sales VALUES (1, 42, 2, 75, 'Customer', '2026-01-01')")
    conn.commit()
    conn.close()
    env = {**os.environ, "DATABASE_PATH": str(database)}
    processes = [subprocess.Popen(
        [sys.executable, "-c", "import db; db.init_db()"],
        cwd=Path(db.__file__).parent, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ) for _ in range(4)]
    for process in processes:
        stdout, stderr = process.communicate(timeout=60)
        assert process.returncode == 0, stderr.decode()
    conn = sqlite3.connect(database)
    assert conn.execute("SELECT id, quantity, selling_price FROM sales").fetchall() == [(1, 2, 75)]
    assert conn.execute("PRAGMA table_info(sales)").fetchall()[1][3] == 0
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'sales_order_item'").fetchone()[0] == 1
    conn.close()
