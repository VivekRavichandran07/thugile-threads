from db import get_connection, init_db, now_iso

init_db()
conn = get_connection()
conn.execute("DELETE FROM products") # clean empty

products = [
  ("Sanganeri Block Print Kurta", "SKU-SAN-001", "Chudidar", 2499, 10),
  ("Ajrakh Co-ord Set", "SKU-AJR-002", "Chudidar", 3499, 10),
  ("Kalamkari Print Set", "SKU-KAL-003", "Chudidar", 2999, 10),
  ("Acharam Block Print Kurta", "SKU-ACH-004", "Chudidar", 2799, 10),
  ("Vasantha Embroidery Set", "SKU-VAS-005", "Chudidar", 3999, 10),
  ("Thalaikku Workwear", "SKU-THA-006", "Chudidar", 2599, 10),
  ("Meenakari Embroidered Set", "SKU-MEE-007", "Chudidar", 3299, 10),
  ("Thenral Cotton Co-ord", "SKU-THE-008", "Chudidar", 2899, 10),
  ("Pavai Handloom Set", "SKU-PAV-009", "Chudidar", 3199, 10),
  ("Kongu Cotton Coord", "SKU-KON-010", "Chudidar", 2699, 10),
  ("Kanakavalli Silk Co-ord", "SKU-KAN-011", "Silk", 5499, 10),
  ("Thaai Silk Set", "SKU-THS-012", "Silk", 5999, 10),
]

for name, sku, cat, price, qty in products:
    conn.execute("""
      INSERT INTO products (name, sku, category, size, color, image_url, cost_price, selling_price, quantity, reorder_level, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, sku, cat, "M", "Multi", f"/static/storefront/assets/Chudidar/{name.replace(' ', '')}.png", price*0.6, price, qty, 5, now_iso()))

conn.commit()
conn.close()
print("Seeded products - restart Flask")