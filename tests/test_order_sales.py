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
