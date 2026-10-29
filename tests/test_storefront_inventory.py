import sqlite3
from contextlib import closing

import db


def test_startup_does_not_create_demo_products(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "catalog.db"))
    db.init_db()
    with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0


def test_deleted_demo_product_stays_deleted_after_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "catalog.db"))
    db.init_db()
    with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
        conn.execute(
            "INSERT INTO products (name, sku, quantity, created_at) VALUES (?, ?, ?, ?)",
            ("Sanganeri Block Print Kurta", "store-sanganeri-block-print-kurta", 10, db.now_iso()),
        )
        conn.execute(
            "INSERT INTO products (name, sku, quantity, created_at) VALUES (?, ?, ?, ?)",
            ("Real Product", "real-product", 7, db.now_iso()),
        )
        conn.execute("DELETE FROM products WHERE sku = 'store-sanganeri-block-print-kurta'")
    db.init_db()
    db.init_db()
    with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
        assert conn.execute("SELECT name, quantity FROM products").fetchall() == [("Real Product", 7)]
