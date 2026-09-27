import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory.db"),
)


def get_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_carts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            size TEXT NOT NULL DEFAULT 'M',
            price REAL NOT NULL DEFAULT 0,
            qty INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, product_name, size)
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
    order_columns = {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
    for column, definition in (
        ("payment_state", "TEXT NOT NULL DEFAULT 'PENDING'"),
        ("cashfree_order_id", "TEXT"),
        ("shipping_address_json", "TEXT"),
    ):
        if column not in order_columns:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {column} {definition}")
    cart_columns = {row[1] for row in conn.execute("PRAGMA table_info(user_carts)")}
    if "size" not in cart_columns:
        conn.execute("ALTER TABLE user_carts RENAME TO user_carts_legacy")
        conn.execute(
            """
            CREATE TABLE user_carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                size TEXT NOT NULL DEFAULT 'M',
                price REAL NOT NULL DEFAULT 0,
                qty INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, product_name, size)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO user_carts (id, user_id, product_name, size, price, qty)
            SELECT id, user_id, product_name, 'M', price, qty
            FROM user_carts_legacy
            """
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
        ("Gulmohar Set", "store-gulmohar-set", "Chudidar", "M", "Rust", "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.png", 4850),
        ("Neelam Set", "store-neelam-set", "Chudidar", "M", "Indigo", "/static/storefront/assets/Chudidar/image-3.jpg", 3950),
        ("Rosa Set", "store-rosa-set", "Chudidar", "M", "Rose", "/static/storefront/assets/Chudidar/image-2.jpg", 5250),
        ("Maragatham Set", "store-maragatham-set", "Chudidar", "M", "Emerald", "/static/storefront/assets/Chudidar/image-3.jpg", 6150),
        ("Manjal Set", "store-manjal-set", "Chudidar", "M", "Marigold", "/static/storefront/assets/Chudidar/image-1.png", 3650),
        ("Thamarai Set", "store-thamarai-set", "Chudidar", "M", "Terracotta", "/static/storefront/assets/Chudidar/KalamkariPrintSet.png", 4450),
        ("Mayil Set", "store-mayil-set", "Chudidar", "M", "Mulberry", "/static/storefront/assets/Chudidar/ThaaiSilkSet.png", 5950),
        ("Vennila Set", "store-vennila-set", "Chudidar", "M", "Ivory", "/static/storefront/assets/Chudidar/PavaiHandloomSet.png", 5750),
        ("Sanganeri Block Print Kurta", "store-sanganeri-block-print-kurta", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/SanganeriBlockPrintKurta.png", 2499),
        ("Ajrakh Co-ord Set", "store-ajrakh-co-ord-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/AjrakhCoordSet.png", 3499),
        ("Kalamkari Print Set", "store-kalamkari-print-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/KalamkariPrintSet.png", 1999),
        ("Acharam Block Print Kurta", "store-acharam-block-print-kurta", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/AcharamBlockPrintKurta.png", 1799),
        ("Vasantha Embroidery Set", "store-vasantha-embroidery-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/VasanthaEmbroiderySet.png", 3999),
        ("Thalaikku Workwear", "store-thalaikku-workwear", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/ThalaikkuWorkwear.png", 2599),
        ("Meenakari Embroidered Set", "store-meenakari-embroidered-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/MeenakariEmbroideredSet.png", 3299),
        ("Thenral Cotton Co-ord", "store-thenral-cotton-co-ord", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/ThenralCottonCoord.png", 2899),
        ("Pavai Handloom Set", "store-pavai-handloom-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/PavaiHandloomSet.png", 3199),
        ("Kongu Cotton Coord", "store-kongu-cotton-coord", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/KonguCottonCoord.png", 1699),
        ("Kanakavalli Silk Co-ord", "store-kanakavalli-silk-co-ord", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/KanakavalliSilkCoord.png", 5499),
        ("Thaai Silk Set", "store-thaai-silk-set", "Chudidar", "M", "Multi", "/static/storefront/assets/Chudidar/ThaaiSilkSet.png", 5999),
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
    
    conn.commit()
    conn.close()


def now_iso():
    return datetime.utcnow().isoformat()

