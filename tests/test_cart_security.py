import sqlite3

import db
import app as app_module
from app import app


def make_cart_client(tmp_path, monkeypatch):
    database_path = tmp_path / "cart-test.db"
    monkeypatch.setattr(db, "DB_PATH", str(database_path))
    db.init_db()

    conn = db.get_connection()
    user_id = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Cart Customer", "cart-test@example.com", "", "2026-01-01T00:00:00"),
    ).lastrowid
    product_ids = []
    for sku, color, price in (
        ("cart-test-red", "Red", 75),
        ("cart-test-blue", "Blue", 120),
    ):
        product_ids.append(conn.execute(
            """
            INSERT INTO products
                (name, sku, size, color, selling_price, discounted_price, quantity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("Same Kurta", sku, "M", color, price + 25, price, 3, "2026-01-01T00:00:00"),
        ).lastrowid)
    conn.commit()
    conn.close()

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return client, database_path, product_ids


def test_public_catalog_exposes_variant_ids_without_exact_stock(
    tmp_path, monkeypatch
):
    client, _, product_ids = make_cart_client(tmp_path, monkeypatch)

    response = client.get("/api/store/products")
    assert response.status_code == 200
    products = [
        product for product in response.get_json()["products"]
        if product["name"] == "Same Kurta"
    ]
    assert len(products) == 2
    ids_by_color = {product["color"]: product["variants"][0]["id"] for product in products}
    assert ids_by_color == {"Red": product_ids[0], "Blue": product_ids[1]}
    for product in products:
        assert "size_quantities" not in product
        assert product["available_sizes"] == ["M"]


def test_cart_persists_server_price_and_refreshes_from_inventory(
    tmp_path, monkeypatch
):
    client, database_path, product_ids = make_cart_client(tmp_path, monkeypatch)
    response = client.post(
        "/api/user/cart",
        json={"cart": [{"product_id": product_ids[1], "qty": 1, "price": 0.01}]},
    )

    assert response.status_code == 200
    conn = sqlite3.connect(database_path)
    assert conn.execute(
        "SELECT product_id, price, qty FROM user_carts"
    ).fetchone() == (product_ids[1], 120.0, 1)
    conn.execute(
        "UPDATE products SET discounted_price = 99 WHERE id = ?",
        (product_ids[1],),
    )
    conn.commit()
    conn.close()

    cart = client.get("/api/user/cart").get_json()["cart"]
    assert cart == [{
        "product_id": product_ids[1],
        "name": "Same Kurta",
        "size": "M",
        "price": 99.0,
        "image_url": None,
        "qty": 1,
        "available": 1,
    }]


def test_cart_rejects_invalid_quantity_without_replacing_saved_cart(
    tmp_path, monkeypatch
):
    client, database_path, product_ids = make_cart_client(tmp_path, monkeypatch)
    saved = client.post(
        "/api/user/cart",
        json={"cart": [{"product_id": product_ids[0], "qty": 1}]},
    )
    assert saved.status_code == 200

    rejected = client.post(
        "/api/user/cart",
        json={"cart": [{"product_id": product_ids[0], "qty": 4}]},
    )

    assert rejected.status_code == 400
    conn = sqlite3.connect(database_path)
    assert conn.execute(
        "SELECT product_id, qty FROM user_carts"
    ).fetchall() == [(product_ids[0], 1)]
    conn.close()


def test_checkout_resolves_price_and_variant_by_product_id(tmp_path, monkeypatch):
    _, _, product_ids = make_cart_client(tmp_path, monkeypatch)

    items, total = app_module.build_order_items([
        {"product_id": product_ids[1], "qty": 1, "price": 0.01},
    ])

    assert total == 120
    assert items[0]["sku"] == "cart-test-blue"
    assert items[0]["color"] == "Blue"
    assert items[0]["unit_price"] == 120


def test_legacy_cart_migration_maps_only_unambiguous_items(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy-cart-test.db"
    monkeypatch.setattr(db, "DB_PATH", str(database_path))
    db.init_db()

    conn = db.get_connection()
    user_id = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Legacy Customer", "legacy-cart@example.com", "", "2026-01-01T00:00:00"),
    ).lastrowid
    product_id = conn.execute(
        """
        INSERT INTO products (name, sku, size, selling_price, quantity, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Unique Kurta", "legacy-unique", "M", 100, 2, "2026-01-01T00:00:00"),
    ).lastrowid
    for sku, color in (("legacy-red", "Red"), ("legacy-blue", "Blue")):
        conn.execute(
            """
            INSERT INTO products
                (name, sku, size, color, selling_price, quantity, created_at)
            VALUES (?, ?, 'M', ?, 100, 2, ?)
            """,
            ("Ambiguous Kurta", sku, color, "2026-01-01T00:00:00"),
        )
    conn.execute("DROP TABLE user_carts")
    conn.execute(
        """
        CREATE TABLE user_carts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            size TEXT NOT NULL DEFAULT 'M',
            price REAL NOT NULL DEFAULT 0,
            qty INTEGER NOT NULL DEFAULT 1,
            UNIQUE(user_id, product_name, size)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO user_carts (user_id, product_name, size, price, qty)
        VALUES (?, ?, 'M', 5, 1)
        """,
        (user_id, "Unique Kurta"),
    )
    conn.execute(
        """
        INSERT INTO user_carts (user_id, product_name, size, price, qty)
        VALUES (?, 'Ambiguous Kurta', 'M', 5, 1)
        """,
        (user_id,),
    )
    conn.commit()
    conn.close()

    db.init_db()

    conn = db.get_connection()
    migrated = {
        row["product_name"]: row
        for row in conn.execute(
            "SELECT product_id, product_name, price, qty FROM user_carts"
        ).fetchall()
    }
    conn.close()
    assert tuple(migrated["Unique Kurta"]) == (product_id, "Unique Kurta", 5.0, 1)
    assert migrated["Ambiguous Kurta"]["product_id"] is None
