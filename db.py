from image_assets import migrate_image_urls
import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory.db"),
)


def get_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT NOT NULL UNIQUE,
            category TEXT,
            size TEXT,
            color TEXT,
            image_url TEXT,
            cost_price REAL NOT NULL DEFAULT 0,
            selling_price REAL NOT NULL DEFAULT 0,
            discounted_price REAL NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 5,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            cost_price REAL NOT NULL,
            supplier TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            selling_price REAL NOT NULL,
            customer TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_carts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            size TEXT NOT NULL DEFAULT 'M',
            price REAL NOT NULL DEFAULT 0,
            qty INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE(user_id, product_id)
        );

        CREATE TABLE IF NOT EXISTS user_wishlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            image_url TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, product_name)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_number TEXT NOT NULL UNIQUE,
            total_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            payment_state TEXT NOT NULL DEFAULT 'PENDING',
            cashfree_order_id TEXT,
            shipping_address_json TEXT,
            items TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            subscribed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS request_rate_limits (
            route_key TEXT NOT NULL,
            client_key TEXT NOT NULL,
            window_start INTEGER NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (route_key, client_key)
        );

        CREATE TABLE IF NOT EXISTS user_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            address_line_2 TEXT,
            city TEXT NOT NULL,
            pincode TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    # Serialize schema inspection and migration across Gunicorn workers.
    conn.execute("BEGIN IMMEDIATE")
    order_columns = {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
    for column, definition in (
        ("payment_state", "TEXT NOT NULL DEFAULT 'PENDING'"),
        ("cashfree_order_id", "TEXT"),
        ("shipping_address_json", "TEXT"),
    ):
        if column not in order_columns:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {column} {definition}")
    sale_columns = {row[1] for row in conn.execute("PRAGMA table_info(sales)")}
    for column, definition in (("order_id", "INTEGER"), ("order_item_index", "INTEGER"),
                               ("product_name", "TEXT")):
        if column not in sale_columns:
            conn.execute(f"ALTER TABLE sales ADD COLUMN {column} {definition}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS sales_order_item "
                 "ON sales(order_id, order_item_index)")
    # Historical online sales survive catalog deletion and missing legacy IDs.
    sales_info = conn.execute("PRAGMA table_info(sales)").fetchall()
    if next(column for column in sales_info if column[1] == "product_id")[3]:
        indexes = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'index' "
                               "AND tbl_name = 'sales' AND sql IS NOT NULL").fetchall()
        conn.execute("""CREATE TABLE sales_migrated (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            quantity INTEGER NOT NULL,
            selling_price REAL NOT NULL,
            customer TEXT,
            date TEXT NOT NULL,
            order_id INTEGER,
            order_item_index INTEGER,
            product_name TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        )""")
        conn.execute("INSERT INTO sales_migrated SELECT id, "
                     "CASE WHEN EXISTS (SELECT 1 FROM products WHERE products.id = sales.product_id) "
                     "THEN product_id ELSE NULL END, quantity, "
                     "selling_price, customer, date, order_id, order_item_index, product_name FROM sales")
        conn.execute("DROP TABLE sales")
        conn.execute("ALTER TABLE sales_migrated RENAME TO sales")
        for index in indexes:
            conn.execute(index[0])
    cart_columns = {row[1] for row in conn.execute("PRAGMA table_info(user_carts)")}
    if "product_id" not in cart_columns or "size" not in cart_columns:
        legacy_carts = conn.execute("SELECT * FROM user_carts").fetchall()
        legacy_columns = {row[1] for row in conn.execute("PRAGMA table_info(user_carts)")}
        conn.execute("ALTER TABLE user_carts RENAME TO user_carts_legacy")
        conn.execute(
            """
            CREATE TABLE user_carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                size TEXT NOT NULL DEFAULT 'M',
                price REAL NOT NULL DEFAULT 0,
                qty INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                UNIQUE(user_id, product_id)
            )
            """
        )
        for item in legacy_carts:
            product_name = item["product_name"]
            size = item["size"] if "size" in legacy_columns else "M"
            candidates = conn.execute(
                "SELECT id FROM products WHERE name = ? AND COALESCE(size, 'M') = ?",
                (product_name, size),
            ).fetchall()
            product_id = candidates[0]["id"] if len(candidates) == 1 else None
            conn.execute(
                """
                INSERT INTO user_carts
                    (id, user_id, product_id, product_name, size, price, qty)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["user_id"],
                    product_id,
                    product_name,
                    size,
                    item["price"],
                    item["qty"],
                ),
            )
        conn.execute("DROP TABLE user_carts_legacy")
    # Keep existing inventory databases compatible when the storefront adds image support.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
    if "image_url" not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
    if "discounted_price" not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN discounted_price REAL NOT NULL DEFAULT 0")
    conn.execute(
        "UPDATE products SET discounted_price = ROUND(selling_price * 0.9, 2) "
        "WHERE discounted_price IS NULL OR discounted_price <= 0"
    )

    storefront_products = [
        ("Gulmohar Set", "store-gulmohar-set", "Chudidar", "M", "Rust", "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", 4850),
        ("Neelam Set", "store-neelam-set", "Chudidar", "M", "Indigo", "/static/storefront/assets/Chudidar/image-3.webp", 3950),
        ("Rosa Set", "store-rosa-set", "Chudidar", "M", "Rose", "/static/storefront/assets/Chudidar/image-2.webp", 5250),
        ("Maragatham Set", "store-maragatham-set", "Chudidar", "M", "Emerald", "/static/storefront/assets/Chudidar/image-3.webp", 6150),
        ("Manjal Set", "store-manjal-set", "Chudidar", "M", "Marigold", "/static/storefront/assets/Chudidar/image-1.webp", 3650),
        ("Thamarai Set", "store-thamarai-set", "Chudidar", "M", "Terracotta", "/static/storefront/assets/Chudidar/KalamkariPrintSet.webp", 4450),
        ("Mayil Set", "store-mayil-set", "Chudidar", "M", "Mulberry", "/static/storefront/assets/Chudidar/ThaaiSilkSet.webp", 5950),
        ("Vennila Set", "store-vennila-set", "Chudidar", "M", "Ivory", "/static/storefront/assets/Chudidar/PavaiHandloomSet.webp", 5750),
        ("Sanganeri Block Print Kurta", "store-sanganeri-block-print-kurta", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.webp", 2499),
        ("Ajrakh Co-ord Set", "store-ajrakh-co-ord-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/AjrakhCoordSet.webp", 3499),
        ("Kalamkari Print Set", "store-kalamkari-print-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/KalamkariPrintSet.webp", 1999),
        ("Acharam Block Print Kurta", "store-acharam-block-print-kurta", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/AcharamBlockPrintKurta.webp", 1799),
        ("Vasantha Embroidery Set", "store-vasantha-embroidery-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/VasanthaEmbroiderySet.webp", 3999),
        ("Thalaikku Workwear", "store-thalaikku-workwear", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/ThalaikkuWorkwear.webp", 2599),
        ("Meenakari Embroidered Set", "store-meenakari-embroidered-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/MeenakariEmbroideredSet.webp", 3299),
        ("Thenral Cotton Co-ord", "store-thenral-cotton-co-ord", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/ThenralCottonCoord.webp", 2899),
        ("Pavai Handloom Set", "store-pavai-handloom-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/PavaiHandloomSet.webp", 3199),
        ("Kongu Cotton Coord", "store-kongu-cotton-coord", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/KonguCottonCoord.webp", 1699),
        ("Kanakavalli Silk Co-ord", "store-kanakavalli-silk-co-ord", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/KanakavalliSilkCoord.webp", 5499),
        ("Thaai Silk Set", "store-thaai-silk-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/ThaaiSilkSet.webp", 5999),
    ]
    for name, sku, category, size, color, image_url, selling_price in storefront_products:
        conn.execute(
            """
            INSERT OR IGNORE INTO products
                (name, sku, category, size, color, image_url, cost_price, selling_price,
                 discounted_price, quantity, reorder_level, created_at)
            SELECT ?, ?, ?, ?, ?, ?, 0, ?, ?, 10, 5, ?
            WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = ?)
            """,
            (name, sku, category, size, color, image_url, selling_price,
             round(selling_price * 0.9, 2), now_iso(), name),
        )
    
    # IMPORTANT: Set all storefront products to quantity=10 if they're currently 0
    # This ensures products show on the storefront after init_db runs
    conn.execute(
        "UPDATE products SET quantity = 10 WHERE sku LIKE 'store-%' AND quantity = 0"
    )
    
    # Add phone column to users if missing
    user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "is_admin" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    if "phone" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")
    if "address" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN address TEXT")
    if "city" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN city TEXT")
    if "pincode" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN pincode TEXT")
    if "google_id" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
    
    # Add user_addresses table if not exists
    address_columns = {row[1] for row in conn.execute("PRAGMA table_info(user_addresses)")}
    if "email" not in address_columns:
        conn.execute("ALTER TABLE user_addresses ADD COLUMN email TEXT")
    if "address_line_2" not in address_columns:
        conn.execute("ALTER TABLE user_addresses ADD COLUMN address_line_2 TEXT")
    
    migrate_image_urls(conn)
    conn.commit()
    conn.close()


def now_iso():
    return datetime.utcnow().isoformat()
