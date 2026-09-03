import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
import os
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
        SELECT id, name, sku, category, size, color, selling_price, quantity, image_url
        FROM products
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    conn.close()
    return jsonify({
        "products": [
            {
                "id": product["id"],
                "name": product["name"],
                "sku": product["sku"],
                "category": product["category"] or "Chudidar",
                "size": product["size"] or "",
                "color": product["color"] or "",
                "price": product["selling_price"],
                "image_url": product["image_url"] or "",
                "in_stock": product["quantity"] > 0,
            }
            for product in rows
        ]
    })


# ---------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------
@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), now_iso()),
        )
        conn.commit()
        user = conn.execute("SELECT id, name, email FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        return jsonify({"user": {"id": user["id"], "name": user["name"], "email": user["email"]}})
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists."}), 409
    finally:
        conn.close()


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    return jsonify({"user": {"id": user["id"], "name": user["name"], "email": user["email"]}})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def auth_me():
    if "user_id" not in session:
        return jsonify({"user": None})
    return jsonify({"user": {"id": session["user_id"], "name": session.get("user_name"), "email": session.get("user_email")}})


# ---------------------------------------------------------------
# USER CART & WISHLIST
# ---------------------------------------------------------------
@app.route("/api/user/cart", methods=["GET"])
def user_cart_get():
    if "user_id" not in session:
        return jsonify({"cart": []})
    conn = get_connection()
    rows = conn.execute(
        "SELECT product_name, price, qty FROM user_carts WHERE user_id = ?",
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
    for item in cart:
        conn.execute(
            "INSERT INTO user_carts (user_id, product_name, price, qty) VALUES (?, ?, ?, ?)",
            (session["user_id"], item.get("name", ""), float(item.get("price", 0)), int(item.get("qty", 1))),
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
    return render_template("products.html", products=all_products)


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

            conn.execute(
                """
                INSERT INTO products
                    (name, sku, category, size, color, image_url, cost_price, selling_price, quantity, reorder_level, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.form["name"].strip(),
                    request.form["sku"].strip(),
                    request.form.get("category", "").strip(),
                    request.form.get("size", "").strip(),
                    request.form.get("color", "").strip(),
                    image_url,
                    float(request.form["cost_price"]),
                    float(request.form["selling_price"]),
                    int(request.form.get("quantity", 0)),
                    int(request.form.get("reorder_level", 5)),
                    now_iso(),
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

            conn.execute(
                """
                UPDATE products
                SET name = ?, sku = ?, category = ?, size = ?, color = ?, image_url = ?,
                    cost_price = ?, selling_price = ?, quantity = ?, reorder_level = ?
                WHERE id = ?
                """,
                (
                    request.form["name"].strip(),
                    request.form["sku"].strip(),
                    request.form.get("category", "").strip(),
                    request.form.get("size", "").strip(),
                    request.form.get("color", "").strip(),
                    image_url,
                    float(request.form["cost_price"]),
                    float(request.form["selling_price"]),
                    int(request.form.get("quantity", 0)),
                    int(request.form.get("reorder_level", 5)),
                    product_id,
                ),
            )
            conn.commit()
            flash(f'Product "{request.form["name"]}" updated.', "success")
            conn.close()
            return redirect(url_for("products"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as e:
            flash(f"Error updating product: {e}", "error")
            conn.close()
            return render_template("edit_product.html", product=product)
    else:
        conn.close()

    return render_template("edit_product.html", product=product)


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


@app.route("/shop/checkout")
def checkout():
    return render_template("checkout.html")


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
