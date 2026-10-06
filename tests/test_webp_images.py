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
