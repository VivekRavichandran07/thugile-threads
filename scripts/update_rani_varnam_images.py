"""Set the Rani Varnam cover after its gallery files are available."""

from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3


def main():
    root = Path.cwd()
    prefix = "/static/storefront/assets/Chudidar/"
    for number in range(1, 6):
        image = root / prefix.lstrip("/") / f"RaniVarnam{number}.webp"
        if not image.is_file():
            raise FileNotFoundError(image)
    cover = prefix + "RaniVarnam1.webp"
    path = Path(os.environ.get("DATABASE_PATH") or root / "inventory.db").resolve(strict=True)
    uri = f"{path.as_uri()}?mode=rw"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        where = "name = 'Rani Varnam' COLLATE NOCASE"
        if not conn.execute(f"SELECT 1 FROM products WHERE {where}").fetchone():
            raise RuntimeError(f"No Rani Varnam product rows in {path}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(f"{path.stem}-before-rani-varnam-{stamp}.db")
        with closing(sqlite3.connect(uri, uri=True)) as source:
            with closing(sqlite3.connect(backup)) as destination:
                source.backup(destination)
        changed = conn.execute(
            f"UPDATE products SET image_url = ? WHERE {where} AND image_url IS NOT ?",
            (cover, cover),
        ).rowcount
        wishlists = conn.execute(
            "UPDATE user_wishlists SET image_url = ? "
            "WHERE product_name = 'Rani Varnam' COLLATE NOCASE AND image_url IS NOT ?",
            (cover, cover),
        ).rowcount
    print(f"{path}: updated {changed} products and {wishlists} wishlist rows")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
