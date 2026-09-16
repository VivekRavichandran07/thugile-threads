import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
import os
import re
from urllib.parse import unquote
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection, init_db, now_iso

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key-please-use-a-random-secret"
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "webp"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
init_db()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


def parse_date(iso_str):
    return datetime.fromisoformat(iso_str)


def parse_product_prices(form):
    selling_price = float(form["selling_price"])
    discounted_price = float(form.get("discounted_price") or selling_price)
    if discounted_price < 0 or discounted_price > selling_price:
        raise ValueError("Discounted price must be between ₹0 and the selling price.")
    return selling_price, discounted_price


def product_image_variants(name, image_url):
    assets_dir = os.path.join(app.static_folder, "storefront", "assets", "Chudidar")
    image_path = unquote((image_url or "").split("?", 1)[0])
    raw_image_stem = os.path.splitext(os.path.basename(image_path))[0].lower()
    if "_" in raw_image_stem:
        raw_image_stem = raw_image_stem.split("_", 1)[-1]
    image_stem = re.sub(r"[^a-z0-9]", "", raw_image_stem)
    normalized_name = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    variants = []
    for filename in os.listdir(assets_dir):
        stem, extension = os.path.splitext(filename)
        if ":" in filename or extension.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        normalized_stem = re.sub(r"[^a-z0-9]", "", stem.lower())
        matches_image = image_stem and (
            normalized_stem == image_stem
            or re.fullmatch(rf"{re.escape(image_stem)}\d+", normalized_stem)
        )
        matches_name = not image_stem and (
            normalized_stem == normalized_name
            or normalized_stem.startswith(normalized_name)
        )
        if matches_image or matches_name:
            variants.append("/static/storefront/assets/Chudidar/" + filename)
    if not variants and image_url:
        variants.append(image_url)
    return sorted(
        variants,
        key=lambda path: (
            1 if re.search(r"-\d+\.[a-z0-9]+$", path, re.I) else 0,
            path.lower(),
        ),
    )


# ---------------------------------------------------------------
# STOREFRONT
# ---------------------------------------------------------------
@app.route("/shop/")
def shop():
    """Serve the public boutique from the same app as the inventory system."""
    return send_from_directory(os.path.join(app.static_folder, "storefront"), "index.html")


@app.route("/api/store/products")
def storefront_products():
    """Public catalog endpoint. Cost prices and raw stock totals stay private."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, name, sku, category, size, color, selling_price, discounted_price,
               quantity, image_url, created_at
        FROM products
        WHERE quantity > 0
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    conn.close()
    grouped = {}
    for product in rows:
        key = (product["name"], product["color"] or "")
        item = grouped.setdefault(key, {
            "id": product["id"], "name": product["name"], "sku": product["sku"],
            "category": product["category"] or "Chudidar", "color": product["color"] or "",
            "price": product["selling_price"], "discounted_price": product["discounted_price"] or product["selling_price"],
            "image_url": product["image_url"] or "", "created_at": product["created_at"],
            "available_sizes": [], "size_quantities": {}, "image_variants": product_image_variants(product["name"], product["image_url"] or ""),
        })
        size = product["size"] or "M"
        item["size_quantities"][size] = item["size_quantities"].get(size, 0) + product["quantity"]
        if product["quantity"] > 0 and size not in item["available_sizes"]:
            item["available_sizes"].append(size)
    return jsonify({
        "products": [
            {**product, "size": ", ".join(product["available_sizes"]), "in_stock": True}
            for product in grouped.values()
            if product["available_sizes"]
        ]
    })


# ---------------------------------------------------------------
# PASSWORD RESET PAGE
# ---------------------------------------------------------------
@app.route("/shop/reset-password")
def reset_password_page():
    return send_from_directory(os.path.join(app.static_folder, "storefront"), "reset-password.html")


# ---------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------
@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""
    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, email, phone, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, generate_password_hash(password), now_iso()),
        )
        conn.commit()
        user = conn.execute("SELECT id, name, email, phone, address, city, pincode FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["user_phone"] = user["phone"]
        session["user_address"] = user["address"] if user["address"] else None
        session["user_city"] = user["city"] if user["city"] else None
        session["user_pincode"] = user["pincode"] if user["pincode"] else None
        return jsonify({"user": {"id": user["id"], "name": user["name"], "email": user["email"], "phone": user["phone"], "address": user["address"] if user["address"] else None, "city": user["city"] if user["city"] else None, "pincode": user["pincode"] if user["pincode"] else None}})
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email or phone already exists."}), 409
    finally:
        conn.close()


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json() or {}
    identifier = (data.get("email") or data.get("phone") or "").strip()
    password = data.get("password") or ""
    if not identifier or not password:
        return jsonify({"error": "Email/phone and password are required."}), 400
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ? OR phone = ?",
        (identifier.lower(), identifier)
    ).fetchone()
    conn.close()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials."}), 401
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_phone"] = user["phone"]
    session["user_address"] = user["address"] if user["address"] else None
    session["user_city"] = user["city"] if user["city"] else None
    session["user_pincode"] = user["pincode"] if user["pincode"] else None
    return jsonify({"user": {"id": user["id"], "name": user["name"], "email": user["email"], "phone": user["phone"], "address": user["address"] if user["address"] else None, "city": user["city"] if user["city"] else None, "pincode": user["pincode"] if user["pincode"] else None}})


@app.route("/api/auth/check-user", methods=["POST"])
def auth_check_user():
    data = request.get_json() or {}
    identifier = (data.get("identifier") or "").strip()
    if not identifier:
        return jsonify({"error": "Email or phone required"}), 400
    conn = get_connection()
    user = conn.execute(
        "SELECT id, name, email, phone FROM users WHERE email = ? OR phone = ?",
        (identifier.lower(), identifier)
    ).fetchone()
    conn.close()
    if user:
        return jsonify({"exists": True, "user": dict(user)})
    return jsonify({"exists": False})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return jsonify({"ok": True})


@app.route("/api/auth/update-profile", methods=["POST"])
def auth_update_profile():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    city = (data.get("city") or "").strip()
    pincode = (data.get("pincode") or "").strip()
    if not name or not phone or not address or not city or not pincode:
        return jsonify({"error": "Name, phone, address, city and pincode are required."}), 400
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET name = ?, phone = ?, address = ?, city = ?, pincode = ? WHERE id = ?",
            (name, phone, address, city, pincode, session["user_id"]),
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/user/addresses", methods=["GET"])
def user_addresses_get():
    if "user_id" not in session:
        return jsonify({"addresses": []})
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM user_addresses WHERE user_id = ? ORDER BY is_default DESC, created_at DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify({"addresses": [dict(row) for row in rows]})


@app.route("/api/user/addresses", methods=["POST"])
def user_addresses_add():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    address_line_2 = (data.get("address_line_2") or "").strip()
    city = (data.get("city") or "").strip()
    pincode = (data.get("pincode") or "").strip()
    if not name or not email or not phone or not address or not city or not pincode:
        return jsonify({"error": "All required address fields are required."}), 400
    conn = get_connection()
    try:
        if data.get("is_default"):
            conn.execute("UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (session["user_id"],))
        conn.execute(
            "INSERT INTO user_addresses (user_id, name, email, phone, address, address_line_2, city, pincode, is_default, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], name, email, phone, address, address_line_2, city, pincode, 1 if data.get("is_default") else 0, now_iso()),
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/user/addresses/<int:address_id>", methods=["GET"])
def user_addresses_get_single(address_id):
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    conn = get_connection()
    try:
        addr = conn.execute("SELECT * FROM user_addresses WHERE id = ? AND user_id = ?", (address_id, session["user_id"])).fetchone()
        if not addr:
            return jsonify({"error": "Address not found"}), 404
        return jsonify({"address": dict(addr)})
    finally:
        conn.close()


@app.route("/api/user/addresses/<int:address_id>", methods=["DELETE"])
def user_addresses_delete(address_id):
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    conn = get_connection()
    try:
        # Check if address belongs to user
        addr = conn.execute("SELECT id, is_default FROM user_addresses WHERE id = ? AND user_id = ?", (address_id, session["user_id"])).fetchone()
        if not addr:
            return jsonify({"error": "Address not found"}), 404
        # If deleting the default address, we need to set another as default or leave none
        if addr["is_default"]:
            # Try to set another address as default
            other = conn.execute("SELECT id FROM user_addresses WHERE user_id = ? AND id != ? LIMIT 1", (session["user_id"], address_id)).fetchone()
            if other:
                conn.execute("UPDATE user_addresses SET is_default = 1 WHERE id = ?", (other["id"],))
        conn.execute("DELETE FROM user_addresses WHERE id = ?", (address_id,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/user/addresses/<int:address_id>/set-default", methods=["POST"])
def user_addresses_set_default(address_id):
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    conn = get_connection()
    try:
        # Check if address exists and belongs to user
        addr = conn.execute("SELECT id FROM user_addresses WHERE id = ? AND user_id = ?", (address_id, session["user_id"])).fetchone()
        if not addr:
            return jsonify({"error": "Address not found"}), 404
        conn.execute("UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (session["user_id"],))
        conn.execute("UPDATE user_addresses SET is_default = 1 WHERE id = ?", (address_id,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/auth/me")
def auth_me():
    if "user_id" not in session:
        return jsonify({"user": None})
    return jsonify({"user": {"id": session["user_id"], "name": session.get("user_name"), "email": session.get("user_email"), "phone": session.get("user_phone"), "address": session.get("user_address"), "city": session.get("user_city"), "pincode": session.get("user_pincode")}})


# ---------------------------------------------------------------
# USER CART & WISHLIST
# ---------------------------------------------------------------
@app.route("/api/user/cart", methods=["GET"])
def user_cart_get():
    if "user_id" not in session:
        return jsonify({"cart": []})
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT product_name, size, MAX(price) AS price, SUM(qty) AS qty
        FROM user_carts
        WHERE user_id = ?
        GROUP BY product_name, size
        """,
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify({"cart": [dict(row) for row in rows]})


@app.route("/api/user/cart", methods=["POST"])
def user_cart_save():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json() or {}
    cart = data.get("cart", [])
    conn = get_connection()
    conn.execute("DELETE FROM user_carts WHERE user_id = ?", (session["user_id"],))
    merged_cart = {}
    for item in cart:
        name = item.get("name", "")
        size = item.get("size") or "M"
        key = (name, size)
        if key not in merged_cart:
            merged_cart[key] = {
                "price": float(item.get("price", 0)),
                "qty": 0,
            }
        merged_cart[key]["qty"] += int(item.get("qty", 1))
    for (name, size), item in merged_cart.items():
        conn.execute(
            "INSERT INTO user_carts (user_id, product_name, size, price, qty) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], name, size, item["price"], item["qty"]),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/user/wishlist", methods=["GET"])
def user_wishlist_get():
    if "user_id" not in session:
        return jsonify({"wishlist": []})
    conn = get_connection()
    rows = conn.execute(
        "SELECT product_name, price, image_url FROM user_wishlists WHERE user_id = ?",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify({"wishlist": [dict(row) for row in rows]})


@app.route("/api/user/wishlist", methods=["POST"])
def user_wishlist_save():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json() or {}
    wishlist = data.get("wishlist", [])
    conn = get_connection()
    conn.execute("DELETE FROM user_wishlists WHERE user_id = ?", (session["user_id"],))
    for item in wishlist:
        conn.execute(
            "INSERT INTO user_wishlists (user_id, product_name, price, image_url) VALUES (?, ?, ?, ?)",
            (session["user_id"], item.get("name", ""), float(item.get("price", 0)), item.get("image_url", "")),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/newsletter/subscribe", methods=["POST"])
def subscribe_newsletter():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO subscribers (email, subscribed_at) VALUES (?, ?)",
            (email, now_iso()),
        )
        conn.commit()
        return jsonify({"ok": True, "message": "Subscribed successfully"})
    finally:
        conn.close()


@app.route("/api/newsletter/subscribers")
def list_subscribers():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    conn = get_connection()
    rows = conn.execute("SELECT email, subscribed_at FROM subscribers ORDER BY subscribed_at DESC").fetchall()
    conn.close()
    return jsonify({"subscribers": [dict(r) for r in rows]})


# ---------------------------------------------------------------
# PASSWORD RESET
# ---------------------------------------------------------------
@app.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Email required"}), 400
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    import secrets
    token = secrets.token_hex(32)
    expires = (datetime.utcnow()).isoformat()
    conn.execute(
        "INSERT INTO password_resets (user_id, token, expires_at, used, created_at) VALUES (?, ?, ?, 0, ?)",
        (user["id"], token, expires, now_iso()),
    )
    conn.commit()
    conn.close()
    reset_link = f"/shop/reset-password?token={token}"
    return jsonify({"ok": True, "reset_link": reset_link})


@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    token = (data.get("token") or "").strip()
    new_password = (data.get("password") or "").strip()
    if not token or not new_password:
        return jsonify({"error": "Token and password required"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM password_resets WHERE token = ? AND used = 0 AND expires_at > ?",
        (token, now_iso()),
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Invalid or expired token"}), 400
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), row["user_id"]),
    )
    conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "Password reset successfully"})


# ---------------------------------------------------------------
# ORDERS
# ---------------------------------------------------------------
@app.route("/api/orders", methods=["GET"])
def orders_get():
    if "user_id" not in session:
        return jsonify({"orders": []})
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify({"orders": [dict(row) for row in rows]})


@app.route("/api/orders", methods=["POST"])
def orders_create():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json() or {}
    items = data.get("items", [])
    total = data.get("total", 0)
    if not items:
        return jsonify({"error": "No items in order"}), 400
    order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{session['user_id']}"
    import json
    conn = get_connection()
    conn.execute(
        "INSERT INTO orders (user_id, order_number, total_amount, status, items, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session["user_id"], order_number, total, "confirmed", json.dumps(items), now_iso()),
    )
    conn.commit()
    conn.execute("DELETE FROM user_carts WHERE user_id = ?", (session["user_id"],))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "order_number": order_number})


# ---------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------
@app.route("/admin/")
def dashboard():
    if "user_id" not in session:
        return render_template("dashboard.html", show_login=True)
    conn = get_connection()
    products = conn.execute("SELECT * FROM products").fetchall()

    total_products = len(products)
    total_stock_units = sum(p["quantity"] for p in products)
    total_stock_value = round(sum(p["quantity"] * p["cost_price"] for p in products), 2)

    sales = conn.execute("SELECT * FROM sales").fetchall()
    total_sales_amount = round(sum(s["quantity"] * s["selling_price"] for s in sales), 2)

    low_stock_products = [p for p in products if p["quantity"] <= p["reorder_level"]]

    recent_sales_rows = conn.execute(
        """
        SELECT sales.*, products.name AS product_name
        FROM sales
        LEFT JOIN products ON sales.product_id = products.id
        ORDER BY sales.date DESC
        LIMIT 5
        """
    ).fetchall()
    conn.close()

    recent_sales = [
        {
            "date": parse_date(s["date"]),
            "product_name": s["product_name"] or "—",
            "quantity": s["quantity"],
            "total_amount": round(s["quantity"] * s["selling_price"], 2),
            "customer": s["customer"],
        }
        for s in recent_sales_rows
    ]

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_stock_units=total_stock_units,
        total_stock_value=total_stock_value,
        total_sales_amount=total_sales_amount,
        low_stock_products=low_stock_products,
        recent_sales=recent_sales,
    )


# ---------------------------------------------------------------
# PRODUCTS
# ---------------------------------------------------------------
@app.route("/admin/products")
def products():
    if "user_id" not in session:
        return render_template("products.html", show_login=True)
    conn = get_connection()
    all_products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close()
    groups = {}
    for product in all_products:
        key = (product["name"], product["color"] or "")
        groups.setdefault(key, []).append(product)
    return render_template("products.html", products=all_products, product_groups=list(groups.values()))


@app.route("/admin/products/add", methods=["GET", "POST"])
def add_product():
    if "user_id" not in session:
        if request.method == "POST":
            return redirect(url_for("shop"))
        return render_template("add_product.html", show_login=True)
    if request.method == "POST":
        conn = get_connection()
        try:
            image_url = request.form.get("image_url", "").strip()
            if "product_image" in request.files:
                file = request.files["product_image"]
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_name = f"{now_iso().replace(':', '').replace('.', '')}_{filename}"
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
                    image_url = f"/uploads/{unique_name}"

            selling_price, discounted_price = parse_product_prices(request.form)

            sizes = request.form.getlist("size") or ["M"]
            for size in sizes:
                sku = request.form["sku"].strip()
                if len(sizes) > 1:
                    sku = f"{sku}-{size.lower().replace(' ', '-')}"
                conn.execute(
                    """
                    INSERT INTO products
                        (name, sku, category, size, color, image_url, cost_price, selling_price,
                         discounted_price, quantity, reorder_level, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request.form["name"].strip(), sku,
                        request.form.get("category", "").strip(), size,
                        request.form.get("color", "").strip(), image_url,
                        float(request.form["cost_price"]), selling_price,
                        discounted_price, int(request.form.get("quantity", 0)),
                        int(request.form.get("reorder_level", 5)), now_iso(),
                    ),
                )
            conn.commit()
            flash(f'Product "{request.form["name"]}" added.', "success")
            conn.close()
            return redirect(url_for("products"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as e:
            flash(f"Error adding product: {e}", "error")
            conn.close()

    return render_template("add_product.html")


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    if "user_id" not in session:
        if request.method == "POST":
            return redirect(url_for("shop"))
        conn = get_connection()
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        conn.close()
        if product is None:
            return redirect(url_for("products"))
        return render_template("edit_product.html", product=product, show_login=True)
    conn = get_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    if product is None:
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("products"))
    variants = conn.execute(
        "SELECT * FROM products WHERE name = ? AND COALESCE(color, '') = COALESCE(?, '') ORDER BY id",
        (product["name"], product["color"]),
    ).fetchall()

    if request.method == "POST":
        try:
            image_url = request.form.get("image_url", "").strip()
            if "product_image" in request.files:
                file = request.files["product_image"]
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_name = f"{now_iso().replace(':', '').replace('.', '')}_{filename}"
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
                    image_url = f"/uploads/{unique_name}"

            selling_price, discounted_price = parse_product_prices(request.form)
            for variant in variants:
                quantity = int(request.form.get(f"quantity_{variant['id']}", variant["quantity"]))
                conn.execute(
                    """
                    UPDATE products
                    SET name = ?, category = ?, color = ?, image_url = ?, cost_price = ?,
                        selling_price = ?, discounted_price = ?, quantity = ?, reorder_level = ?
                    WHERE id = ?
                    """,
                    (
                        request.form["name"].strip(),
                        request.form.get("category", "").strip(),
                        request.form.get("color", "").strip(),
                        image_url,
                        float(request.form["cost_price"]),
                        selling_price,
                        discounted_price,
                        quantity,
                        int(request.form.get("reorder_level", 5)),
                        variant["id"],
                    ),
                )
            conn.commit()
            flash(f'Product "{request.form["name"]}" updated.', "success")
            conn.close()
            return redirect(url_for("products"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as e:
            flash(f"Error updating product: {e}", "error")
            conn.close()
            return render_template("edit_product.html", product=product, product_variants=variants)
    else:
        conn.close()

    return render_template("edit_product.html", product=product, product_variants=variants)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    if "user_id" not in session:
        return redirect(url_for("shop"))
    conn = get_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    if product:
        flash(f'Product "{product["name"]}" deleted.', "success")
    return redirect(url_for("products"))


# ---------------------------------------------------------------
# PURCHASES (stock coming IN)
# ---------------------------------------------------------------
@app.route("/admin/purchases")
def purchases():
    if "user_id" not in session:
        return render_template("purchases.html", show_login=True)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT purchases.*, products.name AS product_name
        FROM purchases
        LEFT JOIN products ON purchases.product_id = products.id
        ORDER BY purchases.date DESC
        """
    ).fetchall()
    conn.close()

    all_purchases = [
        {
            "date": parse_date(r["date"]),
            "product_name": r["product_name"] or "—",
            "quantity": r["quantity"],
            "cost_price": r["cost_price"],
            "total_cost": round(r["quantity"] * r["cost_price"], 2),
            "supplier": r["supplier"],
        }
        for r in rows
    ]
    return render_template("purchases.html", purchases=all_purchases)


@app.route("/admin/purchases/add", methods=["GET", "POST"])
def add_purchase():
    if "user_id" not in session:
        if request.method == "POST":
            return redirect(url_for("shop"))
        conn = get_connection()
        all_products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
        conn.close()
        return render_template("add_purchase.html", products=all_products, show_login=True)
    conn = get_connection()
    all_products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()

    if request.method == "POST":
        try:
            product_id = int(request.form["product_id"])
            quantity = int(request.form["quantity"])
            cost_price = float(request.form["cost_price"])
            supplier = request.form.get("supplier", "").strip()

            product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if product is None:
                flash("Product not found.", "error")
            else:
                conn.execute(
                    "INSERT INTO purchases (product_id, quantity, cost_price, supplier, date) VALUES (?, ?, ?, ?, ?)",
                    (product_id, quantity, cost_price, supplier, now_iso()),
                )
                conn.execute(
                    "UPDATE products SET quantity = quantity + ?, cost_price = ? WHERE id = ?",
                    (quantity, cost_price, product_id),
                )
                conn.commit()
                flash(f'Purchase recorded: {quantity} x {product["name"]}.', "success")
                conn.close()
                return redirect(url_for("purchases"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as e:
            flash(f"Error recording purchase: {e}", "error")

    conn.close()
    return render_template("add_purchase.html", products=all_products)


# ---------------------------------------------------------------
# SALES (stock going OUT)
# ---------------------------------------------------------------
@app.route("/admin/sales")
def sales():
    if "user_id" not in session:
        return render_template("sales.html", show_login=True)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT sales.*, products.name AS product_name
        FROM sales
        LEFT JOIN products ON sales.product_id = products.id
        ORDER BY sales.date DESC
        """
    ).fetchall()
    conn.close()

    all_sales = [
        {
            "date": parse_date(r["date"]),
            "product_name": r["product_name"] or "—",
            "quantity": r["quantity"],
            "selling_price": r["selling_price"],
            "total_amount": round(r["quantity"] * r["selling_price"], 2),
            "customer": r["customer"],
        }
        for r in rows
    ]
    return render_template("sales.html", sales=all_sales)


@app.route("/admin/subscribers")
def subscribers():
    if "user_id" not in session:
        return render_template("subscribers.html", subscribers=[], show_login=True)
    conn = get_connection()
    rows = conn.execute(
        "SELECT email, subscribed_at FROM subscribers ORDER BY subscribed_at DESC"
    ).fetchall()
    conn.close()
    return render_template("subscribers.html", subscribers=rows)


@app.route("/admin/subscribers/delete", methods=["POST"])
def delete_subscriber():
    if "user_id" not in session:
        return redirect(url_for("subscribers"))
    email = (request.form.get("email") or "").strip().lower()
    conn = get_connection()
    conn.execute("DELETE FROM subscribers WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    flash("Subscriber removed.", "success")
    return redirect(url_for("subscribers"))


@app.route("/admin/sales/add", methods=["GET", "POST"])
def add_sale():
    if "user_id" not in session:
        if request.method == "POST":
            return redirect(url_for("shop"))
        conn = get_connection()
        all_products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
        conn.close()
        return render_template("add_sale.html", products=all_products, show_login=True)
    conn = get_connection()
    all_products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()

    if request.method == "POST":
        try:
            product_id = int(request.form["product_id"])
            quantity = int(request.form["quantity"])
            selling_price = float(request.form["selling_price"])
            customer = request.form.get("customer", "").strip()

            product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

            if product is None:
                flash("Product not found.", "error")
            elif quantity > product["quantity"]:
                flash(
                    f'Not enough stock for {product["name"]}. Only {product["quantity"]} left.',
                    "error",
                )
            else:
                conn.execute(
                    "INSERT INTO sales (product_id, quantity, selling_price, customer, date) VALUES (?, ?, ?, ?, ?)",
                    (product_id, quantity, selling_price, customer, now_iso()),
                )
                conn.execute(
                    "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                    (quantity, product_id),
                )
                conn.commit()
                flash(f'Sale recorded: {quantity} x {product["name"]}.', "success")
                conn.close()
                return redirect(url_for("sales"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as e:
            flash(f"Error recording sale: {e}", "error")

    conn.close()
    return render_template("add_sale.html", products=all_products)


@app.route("/shop/shipping")
def shipping():
    return send_from_directory(os.path.join(app.static_folder, "storefront"), "shipping.html")


@app.route("/shop/checkout")
def checkout():
    return render_template("checkout.html")


@app.route("/shop/our-story")
def thugil_story():
    return render_template("thugil_story_page.html")


@app.route("/shop/shipping-returns")
def shipping_returns():
    return render_template("shipping_returns.html")


@app.route("/shop/terms")
def terms():
    return render_template("terms.html")


@app.route("/shop/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")


@app.route("/shop/orders")
def orders():
    return render_template("orders.html")


@app.route("/api/orders")
def api_orders():
    if "user_id" not in session:
        return jsonify({"orders": []})
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify({"orders": [dict(row) for row in rows]})


@app.route("/shop/collections")
def collections():
    return render_template("collections.html")


if __name__ == "__main__":
    app.run(debug=True)
