"""Compare existing inventory with Inventory-Dress.xlsx, Sheet1 rows 2-53."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

WORKBOOK_ITEMS = {
    'TTCOLAM00001': ('Twilight Lilac', 'M', 'Lavender', 1270, 1900, 1499, False),
    'TTCOLAM00002': ('Twilight Lilac', 'M', 'Lavender', 1270, 1900, 1499, False),
    'TTCOLAL00003': ('Twilight Lilac', 'L', 'Lavender', 1270, 1900, 1499, False),
    'TTCOLAXL00004': ('Twilight Lilac', 'XL', 'Lavender', 1270, 1900, 1499, False),
    'TTSCBLM00005': ('PonMayil', 'M', 'Blue', 1400, 2100, 1680, False),
    'TTSCREM00006': ('Regal Bloom', 'M', 'Red', 1400, 2100, 1680, False),
    'TTSCPUM00007': ('Purple Peacock', 'M', 'Purple(Kolam)', 1400, 2100, 1680, False),
    'TTSCPUL00008': ('Purple Peacock', 'L', 'Purple(Kolam)', 1400, 2100, 1680, False),
    'TTSCPUXL00009': ('Purple Peacock', 'XL', 'Purple(Kolam)', 1400, 2100, 1680, False),
    'TTPCYGM00010': ('Mango Mist', 'M', 'Yellow-green', 1425, 2140, 1699, False),
    'TTPCBBM00011': ('Karmughil', 'M', 'Brown and orange', 1425, 2140, 1699, False),
    'TTKCGEM00012': ('Pistachio Bloom', 'M', 'Green', 1216, 1820, 1450, False),
    'TTKCLAM00013': ('Lavender Haze', 'M', 'Lavender', 1216, 1820, 1450, False),
    'TTKCPUM00014': ('Rose Wine', 'M', 'Purple', 1216, 1820, 1450, False),
    'TTRSLGM00015': ('Thalir', 'M', 'Light Green', 1235, 1850, 1480, False),
    'TTRSLGL00016': ('Thalir', 'L', 'Light Green', 1235, 1850, 1480, False),
    'TTVAPEM00017': ('Peach Mirage', 'M', 'Peach', 1268, 1900, 1499, False),
    'TTVAPGM00018': ('Pista royale', 'M', 'Pista green', 1268, 1900, 1499, True),
    'TTRSMSM00019': ('Kungumam', 'M', 'Marron and Sandal', 1233, 1850, 1499, False),
    'TTRSMSL00020': ('Kungumam', 'L', 'Marron and Sandal', 1233, 1850, 1499, False),
    'TTRSMSXXL00021': ('Kungumam', 'XXL', 'Marron and Sandal', 1233, 1850, 1499, True),
    'TTRSGSM00022': ('Royal teal', 'M', 'Green and sandal', 1251, 1880, 1499, False),
    'TTRSGSL00023': ('Royal teal', 'L', 'Green and sandal', 1251, 1880, 1499, False),
    'TTRSGSXL00024': ('Royal teal', 'XL', 'Green and sandal', 1251, 1880, 1499, False),
    'TTRSBCM00025': ('Indigo Arrows', 'M', 'Blue Checked', 1264, 1900, 1499, False),
    'TTRSBCL00026': ('Indigo Arrows', 'L', 'Blue Checked', 1264, 1900, 1499, False),
    'TTRSBCXL00027': ('Indigo Arrows', 'XL', 'Blue Checked', 1264, 1900, 1499, False),
    'TTRSGRM00028': ('Rani Varnam', 'M', 'Green with red', 1262, 1900, 1499, False),
    'TTRSGRL00029': ('Rani Varnam', 'L', 'Green with red', 1262, 1900, 1499, False),
    'TTRSGRXL00030': ('Rani Varnam', 'XL', 'Green with red', 1262, 1900, 1499, False),
    'TTRSGOM00031': ('Sundown Olive', 'M', 'Light green with orange', 1262, 1900, 1499, False),
    'TTRSGOL00032': ('Sundown Olive', 'L', 'Light green with orange', 1262, 1900, 1499, False),
    'TTRSGOXL00033': ('Sundown Olive', 'XL', 'Light green with orange', 1262, 1900, 1499, False),
    'TTRSGEM00034': ('Pista Aura - Scallop', 'M', 'green', 1271, 1900, 1499, False),
    'TTRSGEL00035': ('Pista Aura - Scallop', 'L', 'green', 1271, 1900, 1499, False),
    'TTRSGEXL00036': ('Pista Aura - Scallop', 'XL', 'green', 1271, 1900, 1499, False),
    'TTRSGES00037': ('Pista Aura', 'S', 'green', 1271, 1900, 1499, False),
    'TTRSGEM00038': ('Pista Aura', 'M', 'green', 1271, 1900, 1499, False),
    'TTRSGEL00039': ('Pista Aura', 'L', 'green', 1271, 1900, 1499, False),
    'TTRSGEXL00040': ('Pista Aura', 'XL', 'green', 1271, 1900, 1499, False),
    'TTRSGE2XL00041': ('Pista Aura', '2XL', 'green', 1271, 1900, 1499, False),
    'TTRSGE3XL00042': ('Pista Aura', '3XL', 'green', 1271, 1900, 1499, False),
    'TTRSGE4XL00043': ('Pista Aura', '4XL', 'green', 1271, 1900, 1499, False),
    'TTRSLAM00044': ('Orchid Mist', 'M', 'Lavender', 1271, 1900, 1499, False),
    'TTRSLAL00045': ('Orchid Mist', 'L', 'Lavender', 1271, 1900, 1499, False),
    'TTRSLAXL00046': ('Orchid Mist', 'XL', 'Lavender', 1271, 1900, 1499, False),
    'TTRSORM00047': ('Citrus Charm', 'M', 'Orange', 1271, 1900, 1499, False),
    'TTRSORL00048': ('Citrus Charm', 'L', 'Orange', 1271, 1900, 1499, False),
    'TTRSORXL00049': ('Citrus Charm', 'XL', 'Orange', 1271, 1900, 1499, False),
}

OLD_ORCHID_SKUS = {
    "TTRSLAM00044": "TTRSLAM00037",
    "TTRSLAL00045": "TTRSLAL00038",
    "TTRSLAXL00046": "TTRSLAXL00039",
}


def normalized(value):
    return (value or "").strip().casefold()


def compare(conn):
    products = conn.execute("SELECT * FROM products ORDER BY sku").fetchall()
    by_sku = {product["sku"]: product for product in products}
    changes = []
    missing = conflicts = matched = 0
    for sku, (name, size, color, cost, mrp, launch, sold) in WORKBOOK_ITEMS.items():
        product = by_sku.get(sku)
        if product is None:
            missing += 1
            old = by_sku.get(OLD_ORCHID_SKUS.get(sku))
            candidates = [
                f"{p['sku']} ({p['name']} / {p['size']} / {p['color']})"
                for p in products
                if p is old or (normalized(p["name"]) == normalized(name)
                                and normalized(p["size"]) == normalized(size))
            ]
            suffix = f" | possible matches: {', '.join(candidates)}" if candidates else ""
            print(f"MISSING {sku} {name} / {size}{suffix}")
            continue
        if (normalized(product["name"]), normalized(product["size"])) != (
            normalized(name), normalized(size)
        ):
            conflicts += 1
            print(f"CONFLICT {sku}: DB {product['name']} / {product['size']}"
                  f" | workbook {name} / {size}")
            continue
        matched += 1
        expected = {"color": color, "cost_price": cost, "selling_price": mrp,
                    "discounted_price": launch}
        if sold:
            expected["quantity"] = 0
        diff = {field: value for field, value in expected.items() if product[field] != value}
        if diff:
            print(f"UPDATE {sku} {name}: " + ", ".join(
                f"{field} {product[field]!r} -> {value!r}" for field, value in diff.items()
            ))
            changes.append((product["id"], diff))
    extras = [p for p in products if p["sku"] not in WORKBOOK_ITEMS]
    print(f"SKU rows outside workbook: {len(extras)} ({sum(p['sku'].startswith('store-') for p in extras)} sample SKUs)")
    for product in extras:
        if not product["sku"].startswith("store-"):
            print(f"EXTRA {product['sku']} {product['name']} / {product['size']} | stock {product['quantity']}")
    print(f"Summary: {matched} matched, {len(changes)} to update, {missing} missing, {conflicts} conflicts")
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.environ.get("DATABASE_PATH"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.database:
        parser.error("Set DATABASE_PATH or pass --database")
    path = Path(args.database).resolve(strict=True)
    mode = "rw" if args.apply else "ro"
    with sqlite3.connect(f"{path.as_uri()}?mode={mode}", uri=True, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE" if args.apply else "BEGIN")
        print(f"Database: {path}")
        changes = compare(conn)
        if not args.apply:
            print("Preview only.")
            return
        if not changes:
            print("No changes to apply.")
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(f"{path.stem}-before-inventory-dress-{timestamp}.db")
        with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=30) as source:
            with sqlite3.connect(backup) as destination:
                source.backup(destination)
        print(f"Backup: {backup}")
        for product_id, diff in changes:
            assignments = ", ".join(f"{field} = ?" for field in diff)
            conn.execute(f"UPDATE products SET {assignments} WHERE id = ?",
                         (*diff.values(), product_id))
    print(f"Committed {len(changes)} product updates.")


if __name__ == "__main__":
    main()
