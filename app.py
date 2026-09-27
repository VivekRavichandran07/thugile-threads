import sqlite3
import json
import os
import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
from urllib.parse import unquote, urljoin, urlparse
from datetime import datetime
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection, init_db, now_iso


def load_env_file(path):
    try:
        with open(path, encoding="utf-8") as env_file:
            lines = env_file.readlines()
    except FileNotFoundError:
        return

    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        key, separator, value = entry.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        os.environ.setdefault(key, value)


load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = Flask(__name__)
railway_environment = os.environ.get("RAILWAY_ENVIRONMENT")
secret_key = os.environ.get("SECRET_KEY")
if railway_environment and not secret_key:
    raise RuntimeError("Set a strong SECRET_KEY in the Railway service variables.")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "fallback-dev-secret-key")
app.config["UPLOAD_FOLDER"] = os.environ.get(
    "UPLOAD_FOLDER",
    os.path.join(app.static_folder, "uploads"),
)
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "webp"}
DEFAULT_GOOGLE_CLIENT_ID = "296701170942-b4p3gv5us65uape6unq1jtqhsbljdutf.apps.googleusercontent.com"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
init_db()


def get_google_client_id():
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip() or DEFAULT_GOOGLE_CLIENT_ID


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


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
@app.route("/")
@app.route("/shop/")
def shop():
    """Serve the public boutique from the same app as the inventory system."""
    html_path = os.path.join(app.static_folder, "storefront", "index.html")
    with open(html_path, "r") as f:
        page = f.read()
    client_id = escape(get_google_client_id(), quote=True)
    page = re.sub(
        r'(data-client_id\s*=\s*)(["\'])(.*?)\2',
        lambda match: f'{match.group(1)}"{client_id}"',
        page,
        count=1,
        flags=re.IGNORECASE,
    )
    return page


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


@app.route("/api/auth/google/config")
def auth_google_config():
    return jsonify({"client_id": get_google_client_id()})


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    """Handle Sign in with Google using Google Identity Services (GIS).

    The client-side GIS button produces a JWT ID token (credential).
    We verify it with Google on the server and create/update the local user session.
    See: https://codelabs.developers.google.com/codelabs/sign-in-with-google-button
    """
    import requests
    data = request.get_json() or {}
    credential = data.get("credential", "")
    if not credential:
        return jsonify({"error": "Missing Google credential"}), 400
    client_id = get_google_client_id()
    token_info_url = "https://oauth2.googleapis.com/tokeninfo"
    token_response = requests.get(token_info_url, params={"id_token": credential})
    if token_response.status_code != 200:
        return jsonify({"error": "Invalid Google token"}), 401
    token_data = token_response.json()
    google_id = token_data.get("sub", "")
    email = token_data.get("email", "").lower()
    name = token_data.get("name", "")
    if token_data.get("aud") != client_id:
        return jsonify({"error": "Token audience mismatch"}), 401
    if not google_id or not email:
        return jsonify({"error": "Invalid Google user info"}), 401
    conn = get_connection()
    try:
        existing = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
        if existing:
            user = existing
        else:
            existing_email = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if existing_email:
                conn.execute("UPDATE users SET google_id = ? WHERE email = ?", (google_id, email))
                conn.commit()
                user = existing_email
            else:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash, google_id, created_at) VALUES (?, ?, ?, ?, ?)",
                    (name, email, "", google_id, now_iso()),
                )
                conn.commit()
                user = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["user_phone"] = user["phone"] if user["phone"] else None
        session["user_address"] = user["address"] if user["address"] else None
        session["user_city"] = user["city"] if user["city"] else None
        session["pincode"] = user["pincode"] if user["pincode"] else None
    finally:
        conn.close()
    return jsonify({"user": {"id": user["id"], "name": user["name"], "email": user["email"]}})



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
def get_phonepe_settings():
    environment = os.environ.get("PHONEPE_ENV", "sandbox").strip().lower()
    if environment == "sandbox":
        api_base = "https://api-preprod.phonepe.com/apis/pg-sandbox"
        token_url = f"{api_base}/v1/oauth/token"
    elif environment == "production":
        api_base = "https://api.phonepe.com/apis/pg"
        token_url = "https://api.phonepe.com/apis/identity-manager/v1/oauth/token"
    else:
        raise RuntimeError("PHONEPE_ENV must be either 'sandbox' or 'production'.")

    credentials = {
        "client_id": os.environ.get("PHONEPE_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("PHONEPE_CLIENT_SECRET", "").strip(),
        "client_version": os.environ.get("PHONEPE_CLIENT_VERSION", "").strip(),
    }
    if not all(credentials.values()):
        raise RuntimeError(
            "PhonePe is not configured. Set PHONEPE_CLIENT_ID, "
            "PHONEPE_CLIENT_SECRET, and PHONEPE_CLIENT_VERSION."
        )
    public_base_url = os.environ.get("PHONEPE_REDIRECT_BASE_URL", "").strip()
    if public_base_url:
        parsed = urlparse(public_base_url)
        local_sandbox_url = (
            environment == "sandbox"
            and parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        )
        if (
            (parsed.scheme != "https" and not local_sandbox_url)
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(
                "PHONEPE_REDIRECT_BASE_URL must be an HTTPS URL. "
                "Sandbox may use an HTTP localhost URL."
            )
    return api_base, token_url, credentials


def phonepe_access_token(token_url, credentials):
    response = requests.post(
        token_url,
        data={
            **credentials,
            "grant_type": "client_credentials",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if response.status_code == 401:
        raise PhonePeAuthenticationError
    response.raise_for_status()
    token_data = response.json()
    if not isinstance(token_data, dict):
        raise ValueError("PhonePe authorization response was invalid.")
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("PhonePe authorization response did not include an access token.")
    return access_token


def phonepe_authorization_header(token_url, credentials):
    return f"O-Bearer {phonepe_access_token(token_url, credentials)}"


class PhonePeAuthenticationError(Exception):
    pass


def phonepe_redirect_url(order_number):
    redirect_path = url_for(
        "phonepe_payment_return",
        merchantOrderId=order_number,
    )
    public_base_url = os.environ.get("PHONEPE_REDIRECT_BASE_URL", "").strip()
    if public_base_url:
        return urljoin(public_base_url.rstrip("/") + "/", redirect_path.lstrip("/"))
    return url_for(
        "phonepe_payment_return",
        merchantOrderId=order_number,
        _external=True,
    )


def build_order_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items or len(raw_items) > 50:
        raise ValueError("Your cart is empty or contains too many items.")

    merged_items = {}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Invalid cart item.")
        name = item.get("name")
        size = item.get("size") or "M"
        quantity = item.get("qty")
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(size, str)
            or not size.strip()
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity < 1
        ):
            raise ValueError("Invalid cart item.")
        key = (name.strip(), size.strip())
        merged_items[key] = merged_items.get(key, 0) + quantity
        if merged_items[key] > 100:
            raise ValueError("Each product quantity must be 100 or less.")

    conn = get_connection()
    order_items = []
    total = Decimal("0")
    try:
        for (name, size), quantity in merged_items.items():
            variants = conn.execute(
                """
                SELECT discounted_price, selling_price, SUM(quantity) AS stock
                FROM products
                WHERE name = ? AND COALESCE(size, 'M') = ? AND quantity > 0
                GROUP BY discounted_price, selling_price
                """,
                (name, size),
            ).fetchall()
            available_stock = sum(row["stock"] for row in variants)
            if not variants or quantity > available_stock:
                raise ValueError(f"{name} in size {size} is no longer available.")

            prices = {
                Decimal(str(row["discounted_price"] or row["selling_price"]))
                for row in variants
            }
            if len(prices) != 1:
                raise ValueError(f"{name} is unavailable at a consistent price.")
            unit_price = prices.pop()
            if not unit_price.is_finite() or unit_price <= 0:
                raise ValueError(f"{name} has an invalid price.")
            total += unit_price * quantity
            order_items.append({
                "name": name,
                "size": size,
                "qty": quantity,
                "unit_price": float(unit_price),
            })
    except InvalidOperation as error:
        raise ValueError("A cart item has an invalid price.") from error
    finally:
        conn.close()

    total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_paisa = int((total * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if total_paisa < 100:
        raise ValueError("PhonePe checkout requires an order total of at least ₹1.")
    return order_items, total, total_paisa


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


@app.route("/api/payments/phonepe", methods=["POST"])
def phonepe_create_payment():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json() or {}
    try:
        api_base, token_url, credentials = get_phonepe_settings()
        items, total, total_paisa = build_order_items(data.get("items"))
        address_id = data.get("address_id")
        if isinstance(address_id, bool) or not isinstance(address_id, int):
            return jsonify({"error": "Choose a valid shipping address before paying."}), 400

        conn = get_connection()
        try:
            address = conn.execute(
                "SELECT name, email, phone, address, address_line_2, city, pincode "
                "FROM user_addresses WHERE id = ? AND user_id = ?",
                (address_id, session["user_id"]),
            ).fetchone()
            if not address:
                return jsonify({"error": "Choose a valid shipping address before paying."}), 400
        finally:
            conn.close()

        authorization = phonepe_authorization_header(token_url, credentials)
        order_number = f"TNT-{uuid.uuid4().hex}"
        redirect_url = phonepe_redirect_url(order_number)
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO orders
                (user_id, order_number, total_amount, status, payment_state,
                 shipping_address_json, items, created_at)
            VALUES (?, ?, ?, 'pending', 'PENDING', ?, ?, ?)
            """,
            (
                session["user_id"],
                order_number,
                float(total),
                json.dumps(dict(address)),
                json.dumps(items),
                now_iso(),
            ),
        )
        conn.commit()
        conn.close()
        response = requests.post(
            f"{api_base}/checkout/v2/pay",
            json={
                "merchantOrderId": order_number,
                "amount": total_paisa,
                "expireAfter": 1200,
                "paymentFlow": {
                    "type": "PG_CHECKOUT",
                    "merchantUrls": {"redirectUrl": redirect_url},
                },
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": authorization,
            },
            timeout=20,
        )
        response.raise_for_status()
        payment_data = response.json()
        if not isinstance(payment_data, dict):
            raise ValueError("PhonePe payment response was invalid.")
        pay_page_url = payment_data.get("redirectUrl", "")
        if not isinstance(pay_page_url, str) or not pay_page_url:
            raise ValueError("PhonePe did not return a checkout URL.")
        pay_page = urlparse(pay_page_url)
        if pay_page.scheme != "https" or not pay_page.hostname or not pay_page.hostname.endswith(".phonepe.com"):
            raise ValueError("PhonePe returned an invalid checkout URL.")

        conn = get_connection()
        conn.execute(
            "UPDATE orders SET phonepe_order_id = ? WHERE order_number = ? AND user_id = ?",
            (payment_data.get("orderId"), order_number, session["user_id"]),
        )
        conn.commit()
        conn.close()
        return jsonify({
            "merchant_order_id": order_number,
            "redirect_url": pay_page_url,
        })
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except PhonePeAuthenticationError:
        app.logger.error(
            "PhonePe rejected OAuth credentials for the configured %s environment",
            os.environ.get("PHONEPE_ENV", "sandbox").strip().lower(),
        )
        return jsonify({
            "error": (
                "PhonePe rejected the configured credentials. Verify that "
                "PHONEPE_CLIENT_ID, PHONEPE_CLIENT_SECRET, and "
                "PHONEPE_CLIENT_VERSION are a matching Standard Checkout "
                "credential set for the selected environment."
            )
        }), 502
    except ValueError as error:
        if "order_number" not in locals():
            return jsonify({"error": str(error)}), 400
        app.logger.exception("PhonePe payment initiation failed")
        conn = get_connection()
        conn.execute(
            "UPDATE orders SET status = 'payment_failed', payment_state = 'FAILED' "
            "WHERE order_number = ? AND user_id = ? AND payment_state = 'PENDING'",
            (order_number, session["user_id"]),
        )
        conn.commit()
        conn.close()
        return jsonify({"error": "We could not start PhonePe checkout. Please try again."}), 502
    except requests.RequestException:
        app.logger.exception("PhonePe payment initiation failed")
        if "order_number" in locals():
            conn = get_connection()
            conn.execute(
                "UPDATE orders SET status = 'payment_failed', payment_state = 'FAILED' "
                "WHERE order_number = ? AND user_id = ? AND payment_state = 'PENDING'",
                (order_number, session["user_id"]),
            )
            conn.commit()
            conn.close()
        return jsonify({"error": "We could not start PhonePe checkout. Please try again."}), 502


@app.route("/api/payments/phonepe/<merchant_order_id>/status")
def phonepe_payment_status(merchant_order_id):
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    if not re.fullmatch(r"TNT-[a-f0-9]{32}", merchant_order_id):
        return jsonify({"error": "Order not found."}), 404

    conn = get_connection()
    order = conn.execute(
        "SELECT id, order_number, total_amount, status, payment_state "
        "FROM orders WHERE order_number = ? AND user_id = ?",
        (merchant_order_id, session["user_id"]),
    ).fetchone()
    conn.close()
    if not order:
        return jsonify({"error": "Order not found."}), 404
    if order["payment_state"] == "COMPLETED":
        return jsonify({"order_number": merchant_order_id, "state": "COMPLETED"})

    try:
        api_base, token_url, credentials = get_phonepe_settings()
        authorization = phonepe_authorization_header(token_url, credentials)
        response = requests.get(
            f"{api_base}/checkout/v2/order/{merchant_order_id}/status",
            params={"details": "false"},
            headers={
                "Content-Type": "application/json",
                "Authorization": authorization,
            },
            timeout=15,
        )
        response.raise_for_status()
        payment_data = response.json()
        if not isinstance(payment_data, dict):
            raise ValueError("PhonePe status response was invalid.")
        payment_state = payment_data.get("state")
        if payment_state not in {"PENDING", "FAILED", "COMPLETED"}:
            raise ValueError("PhonePe returned an unrecognized payment state.")

        expected_paisa = int(
            (Decimal(str(order["total_amount"])) * 100).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        response_amount = payment_data.get("amount")
        if payment_state == "COMPLETED" and (
            isinstance(response_amount, bool)
            or not isinstance(response_amount, int)
            or response_amount != expected_paisa
        ):
            app.logger.error("PhonePe amount mismatch for order %s", merchant_order_id)
            return jsonify({"error": "Payment verification failed. Contact support."}), 502

        order_status = {
            "COMPLETED": "confirmed",
            "FAILED": "payment_failed",
            "PENDING": "pending",
        }[payment_state]
        conn = get_connection()
        conn.execute(
            """
            UPDATE orders
            SET payment_state = ?, status = ?, phonepe_order_id = COALESCE(?, phonepe_order_id)
            WHERE id = ? AND user_id = ? AND payment_state != 'COMPLETED'
            """,
            (
                payment_state,
                order_status,
                payment_data.get("orderId"),
                order["id"],
                session["user_id"],
            ),
        )
        if payment_state == "COMPLETED":
            conn.execute("DELETE FROM user_carts WHERE user_id = ?", (session["user_id"],))
        stored_state = conn.execute(
            "SELECT payment_state FROM orders WHERE id = ? AND user_id = ?",
            (order["id"], session["user_id"]),
        ).fetchone()["payment_state"]
        conn.commit()
        conn.close()
        return jsonify({"order_number": merchant_order_id, "state": stored_state})
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except PhonePeAuthenticationError:
        app.logger.error(
            "PhonePe rejected OAuth credentials while checking order status "
            "in the configured %s environment",
            os.environ.get("PHONEPE_ENV", "sandbox").strip().lower(),
        )
        return jsonify({
            "error": (
                "PhonePe rejected the configured credentials. Verify that "
                "PHONEPE_CLIENT_ID, PHONEPE_CLIENT_SECRET, and "
                "PHONEPE_CLIENT_VERSION are a matching Standard Checkout "
                "credential set for the selected environment."
            )
        }), 502
    except (requests.RequestException, ValueError, InvalidOperation):
        app.logger.exception("PhonePe status verification failed for order %s", merchant_order_id)
        return jsonify({"error": "We could not verify this payment yet. Please try again."}), 502


@app.route("/shop/payment/phonepe/return")
def phonepe_payment_return():
    return render_template("payment_result.html")


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
