# Catalog replacement preview

Source: Inventory- Dress price sheet.xlsx, Sheet1, rows 2–43.

42 unique garment SKUs across 20 product names will replace the 20 current sample products on the storefront; sample records will remain at stock 0 to preserve references.

## Field mapping

- SKU: Thugile Serial Number
- Name: Name
- Size: Size
- Colour: Colour
- Cost price: Total(cost price), using the supplied values
- Regular price: MRP
- Discounted price: SP( Launching - 20 % Discount)
- Stock: confirmed 0 for Sold, 1 for blank (40 available garments, 2 sold)
- Images: reuse existing catalog images by product name/colour; repeat if needed
- Category: Chudidar, matching the current catalog; material remains recorded in the source sheet

## Products

| Product | Sizes (one entry per garment) | MRP | Launch price |
| --- | --- | ---: | ---: |
| Twilight Lilac | M, M, L, XL | 1900 | 1520 |
| PonMayil | M | 2100 | 1680 |
| Regal Bloom | M | 2100 | 1680 |
| Purple Peacock | M, L, XL | 2100 | 1680 |
| Mango Mist | M | 2140 | 1700 |
| Karmughil | M | 2140 | 1700 |
| Pistachio Bloom | M | 1820 | 1450 |
| Lavender Haze | M | 1820 | 1450 |
| Rose Wine | M | 1820 | 1450 |
| Thalir | M, L | 1850 | 1480 |
| Peach Mirage | M | 1900 | 1520 |
| Pista royale | M | 1900 | 1520 |
| Kungumam | M, L, XXL | 1850 | 1480 |
| Royal teal | M, L, XL | 1880 | 1504 |
| Indigo Arrows | M, L, XL | 1900 | 1520 |
| Rani Varnam | M, L, XL | 1900 | 1520 |
| Sundown Olive | M, L, XL | 1900 | 1520 |
| Pista Aura | M, L, XL | 1900 | 1520 |
| Orchid Mist | M, L, XL | 1900 | 1520 |
| Citrus Charm | M, L, XL | 1900 | 1520 |

## Preservation requirements

The downloaded live snapshot contains 24 orders, 1 sale, 0 purchases and 7 cart rows. Existing orders and sales must be retained. Existing cart references remain; the sample products will be out of stock. Recheck live references and take a fresh backup immediately before applying changes.

Import into the live database in a transaction; do not upload this snapshot over the running database. No database changes have been applied.

Verified on a temporary copy: 42 new SKUs, 40 available garments, 19 visible names (Pista royale is sold out), existing orders and sales retained, rerunning the import makes no changes.
