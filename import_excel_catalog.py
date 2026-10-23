"""Replace the sample storefront catalog. Default: preview only. Uses Python stdlib."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

PRODUCTS = json.loads(r'''[{"name": "Twilight Lilac", "sku": "TTCOLAM00001", "category": "Chudidar", "size": "M", "color": "Lavender", "image_url": "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", "cost_price": 1270, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Twilight Lilac", "sku": "TTCOLAM00002", "category": "Chudidar", "size": "M", "color": "Lavender", "image_url": "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", "cost_price": 1270, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Twilight Lilac", "sku": "TTCOLAL00003", "category": "Chudidar", "size": "L", "color": "Lavender", "image_url": "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", "cost_price": 1270, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Twilight Lilac", "sku": "TTCOLAXL00004", "category": "Chudidar", "size": "XL", "color": "Lavender", "image_url": "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", "cost_price": 1270, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "PonMayil", "sku": "TTSCBLM00005", "category": "Chudidar", "size": "M", "color": "Blue", "image_url": "/static/storefront/assets/Chudidar/image-3.webp", "cost_price": 1400, "selling_price": 2100, "discounted_price": 1680, "quantity": 1}, {"name": "Regal Bloom", "sku": "TTSCREM00006", "category": "Chudidar", "size": "M", "color": "Red", "image_url": "/static/storefront/assets/Chudidar/image-2.webp", "cost_price": 1400, "selling_price": 2100, "discounted_price": 1680, "quantity": 1}, {"name": "Purple Peacock", "sku": "TTSCPUM00007", "category": "Chudidar", "size": "M", "color": "Purple(Kolam)", "image_url": "/static/storefront/assets/Chudidar/image-1.webp", "cost_price": 1400, "selling_price": 2100, "discounted_price": 1680, "quantity": 1}, {"name": "Purple Peacock", "sku": "TTSCPUL00008", "category": "Chudidar", "size": "L", "color": "Purple(Kolam)", "image_url": "/static/storefront/assets/Chudidar/image-1.webp", "cost_price": 1400, "selling_price": 2100, "discounted_price": 1680, "quantity": 1}, {"name": "Purple Peacock", "sku": "TTSCPUXL00009", "category": "Chudidar", "size": "XL", "color": "Purple(Kolam)", "image_url": "/static/storefront/assets/Chudidar/image-1.webp", "cost_price": 1400, "selling_price": 2100, "discounted_price": 1680, "quantity": 1}, {"name": "Mango Mist", "sku": "TTPCYGM00010", "category": "Chudidar", "size": "M", "color": "Yellow-green", "image_url": "/static/storefront/assets/Chudidar/KalamkariPrintSet.webp", "cost_price": 1425, "selling_price": 2140, "discounted_price": 1700, "quantity": 1}, {"name": "Karmughil", "sku": "TTPCBBM00011", "category": "Chudidar", "size": "M", "color": "black-brown", "image_url": "/static/storefront/assets/Chudidar/ThaaiSilkSet.webp", "cost_price": 1425, "selling_price": 2140, "discounted_price": 1700, "quantity": 1}, {"name": "Pistachio Bloom", "sku": "TTKCGEM00012", "category": "Chudidar", "size": "M", "color": "Green", "image_url": "/static/storefront/assets/Chudidar/PavaiHandloomSet.webp", "cost_price": 1216, "selling_price": 1820, "discounted_price": 1450, "quantity": 1}, {"name": "Lavender Haze", "sku": "TTKCLAM00013", "category": "Chudidar", "size": "M", "color": "Lavender", "image_url": "/static/storefront/assets/Chudidar/AjrakhCoordSet.webp", "cost_price": 1216, "selling_price": 1820, "discounted_price": 1450, "quantity": 1}, {"name": "Rose Wine", "sku": "TTKCPUM00014", "category": "Chudidar", "size": "M", "color": "Purple", "image_url": "/static/storefront/assets/Chudidar/AcharamBlockPrintKurta.webp", "cost_price": 1216, "selling_price": 1820, "discounted_price": 1450, "quantity": 1}, {"name": "Thalir", "sku": "TTRSLGM00015", "category": "Chudidar", "size": "M", "color": "Light Green", "image_url": "/static/storefront/assets/Chudidar/VasanthaEmbroiderySet.webp", "cost_price": 1235, "selling_price": 1850, "discounted_price": 1480, "quantity": 1}, {"name": "Thalir", "sku": "TTRSLGL00016", "category": "Chudidar", "size": "L", "color": "Light Green", "image_url": "/static/storefront/assets/Chudidar/VasanthaEmbroiderySet.webp", "cost_price": 1235, "selling_price": 1850, "discounted_price": 1480, "quantity": 1}, {"name": "Peach Mirage", "sku": "TTVAPEM00017", "category": "Chudidar", "size": "M", "color": "Peach", "image_url": "/static/storefront/assets/Chudidar/ThalaikkuWorkwear.webp", "cost_price": 1268, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Pista royale", "sku": "TTVAPGM00018", "category": "Chudidar", "size": "M", "color": "Pista green", "image_url": "/static/storefront/assets/Chudidar/MeenakariEmbroideredSet.webp", "cost_price": 1268, "selling_price": 1900, "discounted_price": 1520, "quantity": 0}, {"name": "Kungumam", "sku": "TTRSMSM00019", "category": "Chudidar", "size": "M", "color": "Marron and Sandal", "image_url": "/static/storefront/assets/Chudidar/ThenralCottonCoord.webp", "cost_price": 1233, "selling_price": 1850, "discounted_price": 1480, "quantity": 1}, {"name": "Kungumam", "sku": "TTRSMSL00020", "category": "Chudidar", "size": "L", "color": "Marron and Sandal", "image_url": "/static/storefront/assets/Chudidar/ThenralCottonCoord.webp", "cost_price": 1233, "selling_price": 1850, "discounted_price": 1480, "quantity": 1}, {"name": "Kungumam", "sku": "TTRSMSXXL00021", "category": "Chudidar", "size": "XXL", "color": "Marron and Sandal", "image_url": "/static/storefront/assets/Chudidar/ThenralCottonCoord.webp", "cost_price": 1233, "selling_price": 1850, "discounted_price": 1480, "quantity": 0}, {"name": "Royal teal", "sku": "TTRSGSM00022", "category": "Chudidar", "size": "M", "color": "Green and sandal", "image_url": "/static/storefront/assets/Chudidar/KonguCottonCoord.webp", "cost_price": 1251, "selling_price": 1880, "discounted_price": 1504, "quantity": 1}, {"name": "Royal teal", "sku": "TTRSGSL00023", "category": "Chudidar", "size": "L", "color": "Green and sandal", "image_url": "/static/storefront/assets/Chudidar/KonguCottonCoord.webp", "cost_price": 1251, "selling_price": 1880, "discounted_price": 1504, "quantity": 1}, {"name": "Royal teal", "sku": "TTRSGSXL00024", "category": "Chudidar", "size": "XL", "color": "Green and sandal", "image_url": "/static/storefront/assets/Chudidar/KonguCottonCoord.webp", "cost_price": 1251, "selling_price": 1880, "discounted_price": 1504, "quantity": 1}, {"name": "Indigo Arrows", "sku": "TTRSBCM00025", "category": "Chudidar", "size": "M", "color": "Blue Checked", "image_url": "/static/storefront/assets/Chudidar/KanakavalliSilkCoord.webp", "cost_price": 1264, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Indigo Arrows", "sku": "TTRSBCL00026", "category": "Chudidar", "size": "L", "color": "Blue Checked", "image_url": "/static/storefront/assets/Chudidar/KanakavalliSilkCoord.webp", "cost_price": 1264, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Indigo Arrows", "sku": "TTRSBCXL00027", "category": "Chudidar", "size": "XL", "color": "Blue Checked", "image_url": "/static/storefront/assets/Chudidar/KanakavalliSilkCoord.webp", "cost_price": 1264, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Rani Varnam", "sku": "TTRSGRM00028", "category": "Chudidar", "size": "M", "color": "Green with red", "image_url": "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", "cost_price": 1262, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Rani Varnam", "sku": "TTRSGRL00029", "category": "Chudidar", "size": "L", "color": "Green with red", "image_url": "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", "cost_price": 1262, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Rani Varnam", "sku": "TTRSGRXL00030", "category": "Chudidar", "size": "XL", "color": "Green with red", "image_url": "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", "cost_price": 1262, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Sundown Olive", "sku": "TTRSGOM00031", "category": "Chudidar", "size": "M", "color": "Light green with orange", "image_url": "/static/storefront/assets/Chudidar/SundownOlive1.webp", "cost_price": 1262, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Sundown Olive", "sku": "TTRSGOL00032", "category": "Chudidar", "size": "L", "color": "Light green with orange", "image_url": "/static/storefront/assets/Chudidar/SundownOlive1.webp", "cost_price": 1262, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Sundown Olive", "sku": "TTRSGOXL00033", "category": "Chudidar", "size": "XL", "color": "Light green with orange", "image_url": "/static/storefront/assets/Chudidar/SundownOlive1.webp", "cost_price": 1262, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Pista Aura", "sku": "TTRSGEM00034", "category": "Chudidar", "size": "M", "color": "green", "image_url": "/static/storefront/assets/Chudidar/image-2.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Pista Aura", "sku": "TTRSGEL00035", "category": "Chudidar", "size": "L", "color": "green", "image_url": "/static/storefront/assets/Chudidar/image-2.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Pista Aura", "sku": "TTRSGEXL00036", "category": "Chudidar", "size": "XL", "color": "green", "image_url": "/static/storefront/assets/Chudidar/image-2.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Orchid Mist", "sku": "TTRSLAM00037", "category": "Chudidar", "size": "M", "color": "Lavender", "image_url": "/static/storefront/assets/Chudidar/image-1.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Orchid Mist", "sku": "TTRSLAL00038", "category": "Chudidar", "size": "L", "color": "Lavender", "image_url": "/static/storefront/assets/Chudidar/image-1.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Orchid Mist", "sku": "TTRSLAXL00039", "category": "Chudidar", "size": "XL", "color": "Lavender", "image_url": "/static/storefront/assets/Chudidar/image-1.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Citrus Charm", "sku": "TTRSORM00040", "category": "Chudidar", "size": "M", "color": "Orange", "image_url": "/static/storefront/assets/Chudidar/KalamkariPrintSet.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Citrus Charm", "sku": "TTRSORL00041", "category": "Chudidar", "size": "L", "color": "Orange", "image_url": "/static/storefront/assets/Chudidar/KalamkariPrintSet.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}, {"name": "Citrus Charm", "sku": "TTRSORXL00042", "category": "Chudidar", "size": "XL", "color": "Orange", "image_url": "/static/storefront/assets/Chudidar/KalamkariPrintSet.webp", "cost_price": 1271, "selling_price": 1900, "discounted_price": 1520, "quantity": 1}]''')
SAMPLE_SKUS = json.loads(r'''["store-gulmohar-set", "store-neelam-set", "store-rosa-set", "store-maragatham-set", "store-manjal-set", "store-thamarai-set", "store-mayil-set", "store-vennila-set", "store-sanganeri-block-print-kurta", "store-ajrakh-co-ord-set", "store-kalamkari-print-set", "store-acharam-block-print-kurta", "store-vasantha-embroidery-set", "store-thalaikku-workwear", "store-meenakari-embroidered-set", "store-thenral-cotton-co-ord", "store-pavai-handloom-set", "store-kongu-cotton-coord", "store-kanakavalli-silk-co-ord", "store-thaai-silk-set"]''')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default=os.environ.get('DATABASE_PATH'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.database:
        parser.error('Set DATABASE_PATH or provide --database PATH')
    path = Path(args.database).resolve(strict=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        existing = {r['sku']: dict(r) for r in conn.execute('SELECT * FROM products')}
        target_skus = {p['sku'] for p in PRODUCTS}
        if len(target_skus) != len(PRODUCTS):
            raise RuntimeError('Duplicate import SKU')
        unexpected = set(existing) - set(SAMPLE_SKUS) - target_skus
        if unexpected:
            raise RuntimeError('Unexpected live SKUs; review before replacement: '+str(sorted(unexpected)))
        imported = target_skus & set(existing)
        if imported:
            print('Import SKUs already exist. No stock or prices changed. Review current inventory before rerunning.')
            return
        missing = set(SAMPLE_SKUS) - set(existing)
        if missing:
            raise RuntimeError('Sample catalog changed; review missing SKUs: '+str(sorted(missing)))
        for p in PRODUCTS:
            if not (p['selling_price'] > 0 and 0 < p['discounted_price'] <= p['selling_price'] and p['cost_price'] >= 0):
                raise RuntimeError('Invalid prices: '+p['sku'])
        print('Retire sample SKUs:', len(SAMPLE_SKUS))
        print('Add garment SKUs:',len(PRODUCTS),'Available garments:',sum(p['quantity'] for p in PRODUCTS))
        print('Names:',len({p['name'] for p in PRODUCTS}),'Sold garments:',sum(p['quantity']==0 for p in PRODUCTS))
        print('Orders, sales, purchases, carts and customer records will be retained.')
        if not args.apply:
            print('PREVIEW ONLY. Add --apply to create a backup and import.')
            return
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = path.with_name(path.stem+'-before-excel-'+stamp+'.db')
        with sqlite3.connect(backup) as dest:
            conn.backup(dest)
        print('Backup:',backup)
        conn.execute('BEGIN IMMEDIATE')
        # Recheck under the write lock to avoid changing a catalog edited since preview.
        current = {r['sku']: dict(r) for r in conn.execute('SELECT * FROM products')}
        if current != existing:
            raise RuntimeError('Catalog changed during preparation; rerun preview.')
        preserved_tables = ('orders','sales','purchases','users','user_carts','user_wishlists','subscribers')
        before = {t:conn.execute('SELECT * FROM '+t+' ORDER BY id').fetchall() for t in preserved_tables}
        for sku in SAMPLE_SKUS:
            conn.execute('UPDATE products SET quantity=0 WHERE sku=?',(sku,))
        columns = tuple(PRODUCTS[0]) + ('reorder_level','created_at')
        sql = 'INSERT INTO products ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')'
        created = datetime.now(timezone.utc).isoformat()
        for p in PRODUCTS:
            conn.execute(sql,tuple(p[k] for k in PRODUCTS[0])+(0,created))
        for table, rows in before.items():
            if conn.execute('SELECT * FROM '+table+' ORDER BY id').fetchall() != rows:
                raise RuntimeError('Unexpected change in '+table)
        if conn.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Foreign key check failed; import rolled back')
        conn.commit()
        print('APPLIED. Sample records retained with stock 0; new garments imported.')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
