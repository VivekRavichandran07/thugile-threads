"""Apply the Citrus Charm, Mango Mist, Scallop and Rose Wine catalog updates."""

from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3


PREFIX = "/static/storefront/assets/Chudidar/"


def main():
    root = Path.cwd()
    for stem in ("PistaAuraScallop", "RoseWine"):
        for number in range(1, 6):
            image = root / PREFIX.lstrip("/") / f"{stem}{number}.webp"
            if not image.is_file():
                raise FileNotFoundError(image)

    path = Path(os.environ.get("DATABASE_PATH") or root / "inventory.db").resolve(strict=True)
    uri = f"{path.as_uri()}?mode=rw"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(f"{path.stem}-before-november-catalog-{stamp}.db")
        with closing(sqlite3.connect(uri, uri=True)) as source:
            with closing(sqlite3.connect(backup)) as destination:
                source.backup(destination)

        for name, category in (("Citrus Charm", "Raw Silk"), ("Mango Mist", "Pure Cotton")):
            conn.execute("UPDATE products SET category = ? WHERE name = ? COLLATE NOCASE",
                         (category, name))

        conn.execute(
            """INSERT INTO products
               (name, sku, category, size, color, cost_price, selling_price,
                discounted_price, quantity, image_url, created_at)
               VALUES ('Rose Wine', 'TTKCPUM00014', 'Ethnic Wear', 'M', 'Purple',
                       1216, 1820, 1450, 1, ?, ?)
               ON CONFLICT(sku) DO NOTHING""",
            (PREFIX + "RoseWine1.webp", datetime.now(timezone.utc).isoformat()),
        )
        restored = conn.execute(
            "UPDATE products SET is_archived = 0 "
            "WHERE sku = 'TTKCPUM00014' AND name = 'Rose Wine' COLLATE NOCASE"
        )
        if restored.rowcount != 1:
            raise RuntimeError("TTKCPUM00014 does not belong to Rose Wine.")
        for name, stem in (("Pista Aura - Scallop", "PistaAuraScallop"), ("Rose Wine", "RoseWine")):
            cover = PREFIX + stem + "1.webp"
            conn.execute("UPDATE products SET image_url = ? WHERE name = ? COLLATE NOCASE",
                         (cover, name))
            conn.execute("UPDATE user_wishlists SET image_url = ? WHERE product_name = ? COLLATE NOCASE",
                         (cover, name))

        rows = conn.execute(
            "SELECT sku, name, category, is_archived, image_url FROM products "
            "WHERE lower(name) IN ('citrus charm','mango mist','pista aura - scallop','rose wine') "
            "ORDER BY name, sku"
        ).fetchall()
    print(f"Updated {path}. Backup: {backup}")
    for row in rows:
        print(*row, sep=" | ")


if __name__ == "__main__":
    main()
