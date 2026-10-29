"""Resolve converted storefront assets without changing unrelated image URLs."""
import os
from urllib.parse import unquote, urlsplit


ASSET_PREFIX = "/static/storefront/assets/Chudidar/"
ASSET_DIR = os.path.join(os.path.dirname(__file__), "static", "storefront", "assets", "Chudidar")


def webp_image_url(url):
    if not url:
        return url
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith(ASSET_PREFIX):
        return url
    filename = unquote(parsed.path[len(ASSET_PREFIX):])
    stem, extension = os.path.splitext(filename)
    if "/" in filename or "\\" in filename or extension.lower() not in {".png", ".jpg", ".jpeg"}:
        return url
    if not os.path.isfile(os.path.join(ASSET_DIR, stem + ".webp")):
        return url
    return url[:len(parsed.path) - len(extension)] + ".webp" + url[len(parsed.path):]


def migrate_image_urls(conn):
    """Update only image URLs, preserving all other persisted product/user data."""
    for table in ("products", "user_wishlists"):
        for row_id, old_url in conn.execute(f"SELECT id, image_url FROM {table}").fetchall():
            new_url = webp_image_url(old_url)
            if new_url != old_url:
                conn.execute(f"UPDATE {table} SET image_url = ? WHERE id = ?", (new_url, row_id))
    # Replace temporary catalog covers with the products' original photos.
    for name, filename in (("Sundown Olive", "SundownOlive1.webp"), ("Indigo Arrows", "IndigoArrows1.webp"), ("Pista royale", "PistaRoyale1.webp"), ("Pista Royale", "PistaRoyale1.webp"), ("Orchid Mist", "OrchidMist1.webp"), ("PonMayil", "MeenakariEmbroideredSet.webp"), ("Purple Peacock", "PurplePeacock1.webp"), ("Pista Aura", "PistaAura1.webp"), ("Royal Teal", "RoyalTeal1.webp")):
        cover = ASSET_PREFIX + filename
        for table, name_column in (("products", "name"), ("user_wishlists", "product_name")):
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if name_column in columns:
                conn.execute(
                    f"UPDATE {table} SET image_url = ? WHERE {name_column} = ? "
                    "AND (image_url IS NULL OR image_url != ?)",
                    (cover, name, cover),
                )
