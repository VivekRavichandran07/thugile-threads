#!/usr/bin/env python3
"""
One-time migration to set all storefront products to quantity=10.
Run this after deploying to ensure products show on the storefront.
"""
import sqlite3
import os

db_path = os.environ.get("DATABASE_PATH", "/data/inventory.db")

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)

# Update all storefront products to have quantity = 10
updated = conn.execute(
    "UPDATE products SET quantity = 10 WHERE sku LIKE 'store-%' AND quantity = 0"
).rowcount
conn.commit()

# Verify
rows = conn.execute(
    "SELECT name, quantity FROM products WHERE sku LIKE 'store-%' ORDER BY name"
).fetchall()

print(f"✓ Updated {updated} products with zero stock")
print("\nStorefront products inventory:")
for name, qty in rows:
    print(f"  {name}: {qty} units")

conn.close()

