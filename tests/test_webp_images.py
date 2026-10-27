import sqlite3

from app import app, product_image_variants
from image_assets import migrate_image_urls, webp_image_url


def test_converted_urls_preserve_suffixes_and_unrelated_images():
    prefix = "/static/storefront/assets/Chudidar/"
    assert webp_image_url(prefix + "mul%20chanderi.png?v=2#photo") == prefix + "mul%20chanderi.webp?v=2#photo"
    for url in (prefix + "missing.png", "/uploads/photo.jpg", "https://example.com/photo.png"):
        assert webp_image_url(url) == url


def test_gallery_uses_five_unique_webp_images():
    images = product_image_variants("Ajrakh Co-ord Set", "/static/storefront/assets/Chudidar/AjrakhCoordSet.png")
    assert len(images) == 5
    assert len(set(images)) == 5
    for image in images:
        assert image.endswith(".webp")
        response = app.test_client().get(image)
        assert response.status_code == 200
        assert response.mimetype == "image/webp"


def test_sundown_olive_gallery_uses_its_five_webp_images():
    images = product_image_variants("Sundown Olive", "/static/storefront/assets/Chudidar/image-3.webp")
    expected = [
        f"/static/storefront/assets/Chudidar/SundownOlive{number}.webp"
        for number in range(1, 6)
    ]
    assert images == expected
    for image in images:
        response = app.test_client().get(image)
        assert response.status_code == 200
        assert response.mimetype == "image/webp"


def test_migration_only_changes_matching_urls_and_is_idempotent():
    conn = sqlite3.connect(":memory:")
    for table in ("products", "user_wishlists"):
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, image_url TEXT, quantity INTEGER)")
        conn.executemany(f"INSERT INTO {table} VALUES (?, ?, ?)", [
            (1, "/static/storefront/assets/Chudidar/image-2.jpg", 7),
            (2, "/uploads/custom.png", 3),
        ])
    migrate_image_urls(conn)
    first = conn.total_changes
    migrate_image_urls(conn)
    assert conn.total_changes == first
    for table in ("products", "user_wishlists"):
        assert conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall() == [
            (1, "/static/storefront/assets/Chudidar/image-2.webp", 7),
            (2, "/uploads/custom.png", 3),
        ]
    conn.close()


def test_sundown_cover_migration_preserves_inventory_and_other_products():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, image_url TEXT, quantity INTEGER)")
    conn.execute("CREATE TABLE user_wishlists (id INTEGER PRIMARY KEY, product_name TEXT, image_url TEXT)")
    old_cover = "/static/storefront/assets/Chudidar/image-3.webp"
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", [
        (1, "Sundown Olive", old_cover, 3),
        (2, "Unchanged Product", old_cover, 7),
    ])
    conn.execute("INSERT INTO user_wishlists VALUES (1, 'Sundown Olive', ?)", (old_cover,))
    migrate_image_urls(conn)
    changes = conn.total_changes
    migrate_image_urls(conn)
    assert conn.total_changes == changes
    cover = "/static/storefront/assets/Chudidar/SundownOlive1.webp"
    assert conn.execute("SELECT image_url, quantity FROM products ORDER BY id").fetchall() == [(cover, 3), (old_cover, 7)]
    assert conn.execute("SELECT image_url FROM user_wishlists").fetchone()[0] == cover
    conn.close()


def test_orchid_mist_gallery_and_new_cover_migrations():
    prefix = "/static/storefront/assets/Chudidar/"
    images = product_image_variants("Orchid Mist", prefix + "image-1.webp")
    assert images == [prefix + f"OrchidMist{i}.webp" for i in range(1, 6)]
    for url in images + [prefix + "MeenakariEmbroideredSet.webp"]:
        response = app.test_client().get(url)
        assert response.status_code == 200
        assert response.mimetype == "image/webp"
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, image_url TEXT, quantity INTEGER)")
    conn.execute("CREATE TABLE user_wishlists (id INTEGER PRIMARY KEY, product_name TEXT, image_url TEXT)")
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", [(1, "Orchid Mist", prefix + "image-1.webp", 3), (2, "PonMayil", prefix + "image-3.webp", 7)])
    migrate_image_urls(conn)
    assert conn.execute("SELECT image_url, quantity FROM products ORDER BY id").fetchall() == [(images[0], 3), (prefix + "MeenakariEmbroideredSet.webp", 7)]
    changes = conn.total_changes
    migrate_image_urls(conn)
    assert conn.total_changes == changes
    conn.close()
