import sqlite3
import json
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from urllib.parse import quote, unquote, urljoin, urlparse
from datetime import datetime, timedelta, timezone
import time
from xml.sax.saxutils import escape as xml_escape
import requests
from flask import Flask, Response, abort, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection, init_db, now_iso
from image_assets import webp_image_url


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
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
railway_environment = os.environ.get("RAILWAY_ENVIRONMENT")
secret_key = os.environ.get("SECRET_KEY")
if railway_environment and not secret_key:
    raise RuntimeError("Set a strong SECRET_KEY in the Railway service variables.")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "fallback-dev-secret-key")
secure_cookie_setting = os.environ.get("SESSION_COOKIE_SECURE")
if secure_cookie_setting is None:
    secure_cookie = bool(railway_environment)
elif secure_cookie_setting.strip().lower() in {"1", "true", "yes", "on"}:
    secure_cookie = True
elif secure_cookie_setting.strip().lower() in {"0", "false", "no", "off"}:
    secure_cookie = False
else:
    raise RuntimeError("SESSION_COOKIE_SECURE must be a boolean value.")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=secure_cookie,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    SESSION_REFRESH_EACH_REQUEST=False,
    PUBLIC_BASE_URL=os.environ.get("PUBLIC_BASE_URL", "https://thugilethreads.store").rstrip("/"),
)
app.config["UPLOAD_FOLDER"] = os.environ.get(
    "UPLOAD_FOLDER",
    os.path.join(app.static_folder, "uploads"),
)
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "webp"}
DEFAULT_GOOGLE_CLIENT_ID = "296701170942-b4p3gv5us65uape6unq1jtqhsbljdutf.apps.googleusercontent.com"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
init_db()


def synchronize_admin_accounts():
    admin_emails = sorted(
        {
            email.strip().lower()
            for email in os.environ.get("ADMIN_EMAILS", "").split(",")
            if email.strip()
        }
    )
    conn = get_connection()
    try:
        if admin_emails:
            placeholders = ",".join("?" for _ in admin_emails)
            matched_count = conn.execute(
                f"SELECT COUNT(*) FROM users WHERE lower(email) IN ({placeholders})",
                admin_emails,
            ).fetchone()[0]
            conn.execute(
                f"UPDATE users SET is_admin = CASE WHEN lower(email) IN ({placeholders}) "
                "THEN 1 ELSE 0 END",
                admin_emails,
            )
            if matched_count != len(admin_emails):
                app.logger.warning(
                    "Some ADMIN_EMAILS values do not match a registered account; "
                    "register those accounts before granting admin access."
                )
        else:
            conn.execute("UPDATE users SET is_admin = 0")
        conn.commit()
    finally:
        conn.close()


synchronize_admin_accounts()


@app.before_request
def require_admin_access():
    if not (
        request.path == "/admin"
        or request.path.startswith("/admin/")
        or request.path == "/api/newsletter/subscribers"
    ):
        return None

    user_id = session.get("user_id")
    conn = get_connection()
    try:
        user = (
            conn.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
            if user_id is not None
            else None
        )
    finally:
        conn.close()

    if user is not None and user["is_admin"]:
        return None

    if request.path == "/api/newsletter/subscribers":
        status_code = 401 if user_id is None else 403
        return jsonify({"error": "Administrator access required."}), status_code

    abort(403)


RATE_LIMITS = {
    "auth_login": (10, 15 * 60),
    "auth_check_user": (20, 15 * 60),
    "auth_register": (5, 60 * 60),
    "forgot_password": (5, 60 * 60),
    "send_contact_message": (5, 60 * 60),
    "subscribe_newsletter": (5, 60 * 60),
}


def csrf_token():
    token = session.get("_csrf_token")
    if not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def enforce_rate_limit(endpoint):
    limit, window_seconds = RATE_LIMITS[endpoint]
    now = int(time.time())
    window_start = now - now % window_seconds
    client_address = request.remote_addr or "unknown"
    client_key = hashlib.sha256(
        f"{app.config['SECRET_KEY']}:{client_address}".encode("utf-8")
    ).hexdigest()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO request_rate_limits (route_key, client_key, window_start, request_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(route_key, client_key) DO UPDATE SET
                request_count = CASE
                    WHEN request_rate_limits.window_start = excluded.window_start
                    THEN request_rate_limits.request_count + 1
                    ELSE 1
                END,
                window_start = excluded.window_start
            """,
            (endpoint, client_key, window_start),
        )
        count = conn.execute(
            "SELECT request_count FROM request_rate_limits WHERE route_key = ? AND client_key = ?",
            (endpoint, client_key),
        ).fetchone()["request_count"]
        conn.execute(
            "DELETE FROM request_rate_limits WHERE window_start < ?",
            (now - 24 * 60 * 60,),
        )
        conn.commit()
    finally:
        conn.close()
    if count > limit:
        return jsonify({"error": "Too many requests. Please try again later."}), 429, {
            "Retry-After": str(window_seconds - (now - window_start))
        }
    return None


@app.before_request
def protect_mutating_requests():
    csrf_token()
    if request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        supplied_token = (
            request.headers.get("X-CSRFToken")
            or request.form.get("csrf_token")
            or ""
        )
        if not hmac.compare_digest(supplied_token, session["_csrf_token"]):
            return jsonify({"error": "Request verification failed. Reload the page and try again."}), 400
    if request.endpoint in RATE_LIMITS:
        return enforce_rate_limit(request.endpoint)
    return None


@app.after_request
def add_security_headers(response):
    # Existing templates use inline scripts, styles and event handlers.
    # Keep those working while restricting external code and blocking embedding.
    response.headers.setdefault("Content-Security-Policy", "; ".join([
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self' https://api.cashfree.com",
        "script-src 'self' 'unsafe-inline' https://accounts.google.com https://sdk.cashfree.com",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https:",
        "connect-src 'self' https://accounts.google.com https://*.cashfree.com",
        "frame-src https://accounts.google.com https://*.cashfree.com",
    ]))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path == "/shop/reset-password":
        response.headers["Referrer-Policy"] = "no-referrer"
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if app.config["SESSION_COOKIE_SECURE"]:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    response.headers["X-CSRF-Token"] = csrf_token()

    if response.mimetype == "text/html":
        html = response.get_data(as_text=True)
        token = escape(session["_csrf_token"], quote=True)
        csrf_meta = f'<meta name="csrf-token" content="{token}">'
        if re.search(r'<meta\s+name=["\']csrf-token["\']', html, re.I):
            html = re.sub(
                r'<meta\s+name=["\']csrf-token["\'][^>]*>',
                csrf_meta,
                html,
                count=1,
                flags=re.I,
            )
        else:
            html = re.sub(r"</head>", f"  {csrf_meta}\n</head>", html, count=1, flags=re.I)
        html = re.sub(
            r"<form\b([^>]*)>",
            lambda match: match.group(0) + (
                f'<input type="hidden" name="csrf_token" value="{token}">'
                if re.search(r"\bmethod\s*=\s*['\"]?post\b", match.group(1), re.I)
                and not re.search(r'name=["\']csrf_token["\']', match.group(0), re.I)
                else ""
            ),
            html,
            flags=re.I,
        )
        response.set_data(html)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers.add("Vary", "Cookie")
    return response


@app.context_processor
def csrf_template_context():
    return {"csrf_token": csrf_token}


def establish_user_session(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_phone"] = user["phone"] if user["phone"] else None
    session["user_address"] = user["address"] if user["address"] else None
    session["user_city"] = user["city"] if user["city"] else None
    session["user_pincode"] = user["pincode"] if user["pincode"] else None


def send_storefront_email(email_message):
    smtp_username = os.environ.get("SMTP_USERNAME", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    except ValueError as error:
        raise ValueError("SMTP_PORT must be a valid port number.") from error
    if (
        not smtp_username
        or not smtp_password
        or not smtp_host
        or smtp_port not in {465, 587}
    ):
        raise ValueError("SMTP credentials and port 465 or 587 must be configured.")

    email_message["From"] = formataddr(("Thugile & Threads", smtp_username))
    if smtp_port == 465:
        smtp_connection = smtplib.SMTP_SSL(
            smtp_host,
            smtp_port,
            timeout=15,
            context=ssl.create_default_context(),
        )
    else:
        smtp_connection = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
    with smtp_connection as smtp:
        if smtp_port == 587:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(email_message)


def page_metadata(path):
    pages = {
        "/": (
            "Thugile & Threads | Chudidar & Indian Occasionwear",
            "Discover thoughtfully made chudidars and Indian occasionwear from Thugile & Threads.",
        ),
        "/shop/": (
            "Thugile & Threads | Chudidar & Indian Occasionwear",
            "Discover thoughtfully made chudidars and Indian occasionwear from Thugile & Threads.",
        ),
        "/shop/collections": (
            "Shop Chudidar Collections | Thugile & Threads",
            "Explore handcrafted chudidar sets, cotton co-ords, and occasionwear from Thugile & Threads.",
        ),
        "/shop/contact": (
            "Contact Thugile & Threads | Customer Care",
            "Contact Thugile & Threads about orders, sizing, collections, or anything else. We would love to help.",
        ),
        "/shop/checkout": (
            "Secure Checkout | Thugile & Threads",
            "Review your order and complete your Thugile & Threads purchase securely.",
        ),
        "/shop/payment/cashfree/return": (
            "Payment Status | Thugile & Threads",
            "View the status of your Thugile & Threads payment.",
        ),
        "/shop/our-story": (
            "Our Story | Thugile & Threads",
            "Learn about the story, craft, and inspiration behind Thugile & Threads.",
        ),
        "/shop/shipping": (
            "My Account, Orders & Shipping | Thugile & Threads",
            "Manage your Thugile & Threads account, saved addresses, and order history.",
        ),
        "/shop/shipping-returns": (
            "Shipping & Returns | Thugile & Threads",
            "Read Thugile & Threads shipping, delivery, and return information before placing an order.",
        ),
        "/shop/terms": (
            "Terms & Conditions | Thugile & Threads",
            "Read the terms and conditions for using the Thugile & Threads website and store.",
        ),
        "/shop/privacy-policy": (
            "Privacy Policy | Thugile & Threads",
            "Learn how Thugile & Threads handles account, order, and contact information.",
        ),
        "/shop/reset-password": (
            "Reset Your Password | Thugile & Threads",
            "Securely reset your Thugile & Threads account password using your private reset link.",
        ),
    }
    return pages.get(path)


def product_item_list_json_ld():
    base_url = app.config["PUBLIC_BASE_URL"]
    page_url = urljoin(base_url + "/", "shop/collections")
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT name, category, color, selling_price, discounted_price, image_url
        FROM products WHERE quantity > 0 ORDER BY name, color, id
        """
    ).fetchall()
    conn.close()
    products = {}
    for row in rows:
        key = (row["name"], row["color"] or "")
        products.setdefault(key, row)
    items = []
    for index, product in enumerate(products.values(), start=1):
        image = product["image_url"] or ""
        structured_product = {
            "@type": "Product",
            "name": product["name"],
            "description": (
                f"{product['color']} {product['category'] or 'Indian wear'} from Thugile & Threads."
                if product["color"]
                else f"{product['category'] or 'Indian wear'} from Thugile & Threads."
            ),
            "url": page_url,
            "offers": {
                "@type": "Offer",
                "priceCurrency": "INR",
                "price": f"{product['discounted_price'] or product['selling_price']:.2f}",
                "availability": "https://schema.org/InStock",
                "url": page_url,
            },
        }
        if image:
            structured_product["image"] = [urljoin(base_url + "/", image.lstrip("/"))]
        items.append({
            "@type": "ListItem",
            "position": index,
            "item": structured_product,
        })
    return json.dumps(
        {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": items},
        ensure_ascii=True,
        separators=(",", ":"),
    ).replace("<", "\\u003c")


@app.after_request
def add_storefront_seo(response):
    seo_path = "/" if request.path in {"/", "/shop/"} else request.path.rstrip("/")
    metadata = page_metadata("/shop/" if request.path == "/shop/" else seo_path)
    if metadata is None or response.mimetype != "text/html":
        return response
    title, description = metadata
    base_url = app.config["PUBLIC_BASE_URL"]
    canonical_path = "/" if request.path in {"/", "/shop/"} else seo_path
    canonical_url = urljoin(base_url + "/", canonical_path.lstrip("/"))
    image_url = urljoin(base_url + "/", "static/storefront/assets/thugile-and-threads-logo.webp")
    html = response.get_data(as_text=True)
    html = re.sub(
        r"<title\b[^>]*>.*?</title>",
        f"<title>{escape(title)}</title>",
        html,
        count=1,
        flags=re.I | re.S,
    )
    html = re.sub(
        r'<meta\s+name=["\']description["\'][^>]*>',
        "",
        html,
        flags=re.I,
    )
    html = re.sub(r'<link\s+rel=["\']canonical["\'][^>]*>', "", html, flags=re.I)
    seo_tags = (
        f'<meta name="description" content="{escape(description, quote=True)}">'
        f'<link rel="canonical" href="{escape(canonical_url, quote=True)}">'
        f'<meta property="og:type" content="website">'
        f'<meta property="og:title" content="{escape(title, quote=True)}">'
        f'<meta property="og:description" content="{escape(description, quote=True)}">'
        f'<meta property="og:url" content="{escape(canonical_url, quote=True)}">'
        f'<meta property="og:image" content="{escape(image_url, quote=True)}">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:title" content="{escape(title, quote=True)}">'
        f'<meta name="twitter:description" content="{escape(description, quote=True)}">'
        f'<meta name="twitter:image" content="{escape(image_url, quote=True)}">'
    )
    for env_name, tag_name in (
        ("GOOGLE_SITE_VERIFICATION", "google-site-verification"),
        ("BING_SITE_VERIFICATION", "msvalidate.01"),
    ):
        verification = os.environ.get(env_name, "").strip()
        if verification:
            seo_tags += f'<meta name="{tag_name}" content="{escape(verification, quote=True)}">'
    if request.path in {"/", "/shop/"}:
        site_identity = json.dumps({
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Thugile & Threads",
            "alternateName": ["Thugile Threads", "thugilethreads.store"],
            "url": base_url + "/",
        }, ensure_ascii=True).replace("<", "\\u003c")
        seo_tags += f'<script type="application/ld+json">{site_identity}</script>'
    if request.path in {
        "/shop/checkout",
        "/shop/shipping",
        "/shop/reset-password",
        "/shop/payment/cashfree/return",
    }:
        seo_tags += '<meta name="robots" content="noindex, nofollow">'
    html = re.sub(r"</head>", f"  {seo_tags}\n</head>", html, count=1, flags=re.I)
    if request.path in {"/", "/shop/", "/shop/collections"}:
        html = re.sub(
            r"</body>",
            f'<script type="application/ld+json">{product_item_list_json_ld()}</script></body>',
            html,
            count=1,
            flags=re.I,
        )
    response.set_data(html)
    return response


def get_google_client_id():
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip() or DEFAULT_GOOGLE_CLIENT_ID


@app.context_processor
def google_auth_template_context():
    return {"google_client_id": get_google_client_id()}


def inject_google_client_id(page):
    client_id = escape(get_google_client_id(), quote=True)
    return re.sub(
        r'(data-client_id\s*=\s*)(["\'])(.*?)\2',
        lambda match: f'{match.group(1)}"{client_id}"',
        page,
        count=1,
        flags=re.IGNORECASE,
    )


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
        if extension.lower() != ".webp" and os.path.isfile(os.path.join(assets_dir, stem + ".webp")):
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
        variants.append(webp_image_url(image_url))
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
    return inject_google_client_id(page)


@app.route("/googled9f82b121fbf0657.html")
def google_search_verification_file():
    response = send_from_directory(
        os.path.join(app.static_folder, "search-verification"),
        "googled9f82b121fbf0657.html",
    )
    response.direct_passthrough = False
    return response


@app.route("/robots.txt")
def robots_txt():
    sitemap_url = urljoin(app.config["PUBLIC_BASE_URL"] + "/", "sitemap.xml")
    return Response(
        "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\n"
        "Disallow: /shop/checkout\nDisallow: /shop/shipping\n"
        "Disallow: /shop/reset-password\nDisallow: /shop/payment/\n"
        f"Sitemap: {sitemap_url}\n",
        mimetype="text/plain",
    )


@app.route("/sitemap.xml")
def sitemap_xml():
    base_url = app.config["PUBLIC_BASE_URL"]
    paths = (
        "/", "/shop/collections", "/shop/contact", "/shop/our-story",
        "/shop/shipping-returns", "/shop/terms", "/shop/privacy-policy",
    )
    locations = "".join(
        f"<url><loc>{xml_escape(urljoin(base_url + '/', path.lstrip('/')))}</loc></url>"
        for path in paths
    )
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{locations}</urlset>",
        mimetype="application/xml",
    )


@app.route("/shop/contact")
@app.route("/shop/contact/")
def contact_page():
    return render_template("contact.html")


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
            "image_url": webp_image_url(product["image_url"] or ""), "created_at": product["created_at"],
            "available_sizes": [], "variants": [], "image_variants": product_image_variants(product["name"], product["image_url"] or ""),
        })
        size = product["size"] or "M"
        if product["quantity"] > 0 and size not in item["available_sizes"]:
            item["available_sizes"].append(size)
            item["variants"].append({
                "id": product["id"],
                "sku": product["sku"],
                "size": size,
                "price": product["selling_price"],
                "discounted_price": product["discounted_price"] or product["selling_price"],
            })
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
    if len(password) < 10:
        return jsonify({"error": "Password must be at least 10 characters."}), 400
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, email, phone, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, generate_password_hash(password), now_iso()),
        )
        conn.commit()
        user = conn.execute("SELECT id, name, email, phone, address, city, pincode FROM users WHERE email = ?", (email,)).fetchone()
        establish_user_session(user)
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
    establish_user_session(user)
    return jsonify({"user": {"id": user["id"], "name": user["name"], "email": user["email"], "phone": user["phone"], "address": user["address"] if user["address"] else None, "city": user["city"] if user["city"] else None, "pincode": user["pincode"] if user["pincode"] else None}})


@app.route("/api/auth/check-user", methods=["POST"])
def auth_check_user():
    data = request.get_json() or {}
    identifier = (data.get("identifier") or "").strip()
    if not identifier:
        return jsonify({"error": "Email or phone required"}), 400
    conn = get_connection()
    user = conn.execute(
        "SELECT 1 FROM users WHERE email = ? OR phone = ?",
        (identifier.lower(), identifier)
    ).fetchone()
    conn.close()
    if user:
        return jsonify({"exists": True})
    return jsonify({"exists": False})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
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
        establish_user_session(user)
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
        SELECT c.product_id, p.name, p.size,
               COALESCE(NULLIF(p.discounted_price, 0), p.selling_price) AS price,
               p.image_url, c.qty,
               CASE WHEN p.quantity >= c.qty THEN 1 ELSE 0 END AS available
        FROM user_carts AS c
        JOIN products AS p ON p.id = c.product_id
        WHERE c.user_id = ?
        ORDER BY c.id
        """,
        (session["user_id"],),
    ).fetchall()
    unresolved_count = conn.execute(
        "SELECT COUNT(*) FROM user_carts WHERE user_id = ? AND product_id IS NULL",
        (session["user_id"],),
    ).fetchone()[0]
    conn.close()
    return jsonify({"cart": [dict(row) for row in rows], "unresolved_count": unresolved_count})


@app.route("/api/user/cart", methods=["POST"])
def user_cart_save():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("cart"), list) or len(data["cart"]) > 50:
        return jsonify({"error": "Invalid cart."}), 400

    merged_cart = {}
    for item in data["cart"]:
        if not isinstance(item, dict):
            return jsonify({"error": "Invalid cart item."}), 400
        product_id = item.get("product_id")
        quantity = item.get("qty")
        if (
            isinstance(product_id, bool)
            or not isinstance(product_id, int)
            or product_id < 1
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity < 1
        ):
            return jsonify({"error": "Invalid cart item."}), 400
        merged_cart[product_id] = merged_cart.get(product_id, 0) + quantity
        if merged_cart[product_id] > 100:
            return jsonify({"error": "Each product quantity must be 100 or less."}), 400

    conn = get_connection()
    validated_items = []
    for product_id, quantity in merged_cart.items():
        product = conn.execute(
            "SELECT id, name, size, quantity FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if not product or product["quantity"] < quantity:
            conn.close()
            return jsonify({"error": "A cart item is no longer available in the requested quantity."}), 400
        price_row = conn.execute(
            "SELECT COALESCE(NULLIF(discounted_price, 0), selling_price) AS price "
            "FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        validated_items.append((product, price_row["price"], quantity))

    conn.execute("DELETE FROM user_carts WHERE user_id = ?", (session["user_id"],))
    for product, price, quantity in validated_items:
        conn.execute(
            """
            INSERT INTO user_carts (user_id, product_id, product_name, size, price, qty)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                product["id"],
                product["name"],
                product["size"] or "M",
                price,
                quantity,
            ),
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


@app.route("/api/contact", methods=["POST"])
def send_contact_message():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Please submit the contact form again."}), 400

    name_value = data.get("name", "")
    email_value = data.get("email", "")
    topic_value = data.get("topic", "General enquiry")
    message_value = data.get("message", "")
    website_value = data.get("website", "")
    if not all(
        isinstance(value, str)
        for value in (name_value, email_value, topic_value, message_value, website_value)
    ):
        return jsonify({"error": "Please check your details and try again."}), 400
    if website_value.strip():
        return jsonify({"ok": True})

    name = name_value.strip()
    email = email_value.strip()
    topic = topic_value.strip() or "General enquiry"
    message = message_value.strip()
    if (
        not name
        or len(name) > 120
        or not email
        or len(email) > 254
        or not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", email)
        or len(topic) > 120
        or not message
        or len(message) > 5000
        or any(ord(char) < 32 and char not in "\t\n\r" for char in name + topic + message)
    ):
        return jsonify({"error": "Please check your details and try again."}), 400

    recipient = os.environ.get("CONTACT_EMAIL", "thugile.official@gmail.com").strip()
    if not recipient:
        app.logger.error(
            "Contact email configuration is invalid; set CONTACT_EMAIL."
        )
        return jsonify({"error": "Email is temporarily unavailable. Please email us directly."}), 503

    email_message = EmailMessage()
    email_message["Subject"] = f"Website contact: {topic}"
    email_message["To"] = recipient
    email_message["Reply-To"] = email
    email_message.set_content(
        f"Name: {name}\nEmail: {email}\nTopic: {topic}\n\nMessage:\n{message}\n"
    )

    try:
        send_storefront_email(email_message)
    except ValueError:
        app.logger.exception("Contact email configuration is invalid.")
        return jsonify({"error": "Email is temporarily unavailable. Please email us directly."}), 503
    except (smtplib.SMTPException, OSError):
        app.logger.exception("Failed to send a storefront contact message.")
        return jsonify({"error": "We couldn't send your message right now. Please try again or email us directly."}), 502

    return jsonify({"ok": True, "message": "Thank you — your message is on its way."})


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
    data = request.get_json(silent=True)
    email = (data.get("email") or "").strip().lower() if isinstance(data, dict) else ""
    if not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", email):
        return jsonify({"error": "Enter a valid email address."}), 400

    generic_response = {
        "ok": True,
        "message": "If an account exists for that email, a password reset link will be sent.",
    }
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id, email FROM users WHERE email = ?", (email,)
        ).fetchone()
        if user:
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            expires = (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).replace(tzinfo=None).isoformat()
            conn.execute(
                "UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0",
                (user["id"],),
            )
            conn.execute(
                """
                INSERT INTO password_resets (user_id, token, expires_at, used, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                (user["id"], token_hash, expires, now_iso()),
            )
            conn.commit()
            reset_link = (
                f"{app.config['PUBLIC_BASE_URL']}/shop/reset-password"
                f"?token={quote(token, safe='')}"
            )
            message = EmailMessage()
            message["To"] = user["email"]
            message["Subject"] = "Reset your Thugile & Threads password"
            message.set_content(
                "We received a request to reset the password for your Thugile & Threads account.\n\n"
                f"Use this link within 30 minutes to choose a new password:\n{reset_link}\n\n"
                "If you did not request this, you can ignore this email. Your password will not change."
            )
            try:
                send_storefront_email(message)
            except ValueError:
                app.logger.exception("Password-reset email configuration is invalid.")
                conn.execute(
                    "UPDATE password_resets SET used = 1 WHERE token = ?",
                    (token_hash,),
                )
                conn.commit()
            except (smtplib.SMTPException, OSError):
                app.logger.exception("Failed to send a password-reset email.")
                conn.execute(
                    "UPDATE password_resets SET used = 1 WHERE token = ?",
                    (token_hash,),
                )
                conn.commit()
    finally:
        conn.close()
    return jsonify(generic_response)


@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid or expired reset token."}), 400
    token = (data.get("token") or "").strip()
    new_password = data.get("password") or ""
    if not token or not new_password:
        return jsonify({"error": "Token and password are required."}), 400
    if len(new_password) < 10:
        return jsonify({"error": "Password must be at least 10 characters."}), 400
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT id, user_id FROM password_resets
            WHERE token = ? AND used = 0 AND expires_at > ?
            """,
            (token_hash, now_iso()),
        ).fetchone()
        if not row:
            conn.rollback()
            return jsonify({"error": "Invalid or expired reset token."}), 400
        updated = conn.execute(
            """
            UPDATE password_resets SET used = 1
            WHERE id = ? AND used = 0 AND expires_at > ?
            """,
            (row["id"], now_iso()),
        )
        if updated.rowcount != 1:
            conn.rollback()
            return jsonify({"error": "Invalid or expired reset token."}), 400
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(new_password), row["user_id"]),
        )
        conn.execute(
            "UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0",
            (row["user_id"],),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "message": "Password reset successfully"})


# ---------------------------------------------------------------
# ORDERS
# ---------------------------------------------------------------
def get_cashfree_settings():
    environment = os.environ.get("CASHFREE_ENV", "production").strip().lower()
    if environment == "sandbox":
        api_base = "https://sandbox.cashfree.com/pg"
    elif environment == "production":
        api_base = "https://api.cashfree.com/pg"
    else:
        raise RuntimeError("CASHFREE_ENV must be either 'sandbox' or 'production'.")

    credentials = {
        "client_id": os.environ.get("CASHFREE_APP_ID", "").strip(),
        "client_secret": os.environ.get("CASHFREE_SECRET_KEY", "").strip(),
    }
    if not all(credentials.values()):
        raise RuntimeError(
            "Cashfree is not configured. Set CASHFREE_APP_ID and CASHFREE_SECRET_KEY."
        )
    public_base_url = os.environ.get("CASHFREE_REDIRECT_BASE_URL", "").strip()
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
                "CASHFREE_REDIRECT_BASE_URL must be an HTTPS URL. "
                "Sandbox may use an HTTP localhost URL."
            )
    return api_base, credentials, environment


def cashfree_api_headers(credentials):
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-client-id": credentials["client_id"],
        "x-client-secret": credentials["client_secret"],
        "x-api-version": "2025-01-01",
    }


def cashfree_error_details(error):
    response = error.response
    if response is None:
        return None
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    details = {"status": response.status_code}
    for key in ("code", "type", "message"):
        value = payload.get(key)
        if isinstance(value, str):
            value = " ".join(value.split())[:250]
            if key == "message":
                value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[redacted]", value)
                value = re.sub(r"\b\d{7,}\b", "[redacted]", value)
            details[key] = value
    return details


def cashfree_return_url(order_number):
    redirect_path = url_for("cashfree_payment_return", order_id=order_number)
    public_base_url = os.environ.get("CASHFREE_REDIRECT_BASE_URL", "").strip()
    if public_base_url:
        return urljoin(public_base_url.rstrip("/") + "/", redirect_path.lstrip("/"))
    return url_for("cashfree_payment_return", order_id=order_number, _external=True)


def build_order_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items or len(raw_items) > 50:
        raise ValueError("Your cart is empty or contains too many items.")

    merged_items = {}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Invalid cart item.")
        product_id = item.get("product_id")
        quantity = item.get("qty")
        if (
            isinstance(product_id, bool)
            or not isinstance(product_id, int)
            or product_id < 1
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity < 1
        ):
            raise ValueError("Invalid cart item.")
        merged_items[product_id] = merged_items.get(product_id, 0) + quantity
        if merged_items[product_id] > 100:
            raise ValueError("Each product quantity must be 100 or less.")

    conn = get_connection()
    order_items = []
    total = Decimal("0")
    try:
        for product_id, quantity in merged_items.items():
            product = conn.execute(
                """
                SELECT id, name, sku, color, size, discounted_price, selling_price, quantity
                FROM products
                WHERE id = ?
                """,
                (product_id,),
            ).fetchone()
            if not product or quantity > product["quantity"]:
                raise ValueError("A cart item is no longer available in the requested quantity.")

            name = product["name"]
            size = product["size"] or "M"
            unit_price = Decimal(str(product["discounted_price"] or product["selling_price"]))
            if not unit_price.is_finite() or unit_price <= 0:
                raise ValueError(f"{name} has an invalid price.")
            total += unit_price * quantity
            order_items.append({
                "product_id": product["id"],
                "sku": product["sku"],
                "name": name,
                "color": product["color"],
                "size": size,
                "qty": quantity,
                "unit_price": float(unit_price),
            })
    except InvalidOperation as error:
        raise ValueError("A cart item has an invalid price.") from error
    finally:
        conn.close()

    total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if total < Decimal("1.00"):
        raise ValueError("Cashfree checkout requires an order total of at least \u20b91.")
    return order_items, total


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


@app.route("/api/payments/cashfree", methods=["POST"])
def cashfree_create_payment():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payment request."}), 400
    try:
        api_base, credentials, environment = get_cashfree_settings()
        items, total = build_order_items(data.get("items"))
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

        order_number = f"TNT-{uuid.uuid4().hex}"
        return_url = cashfree_return_url(order_number)
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO orders
                (user_id, order_number, cashfree_order_id, total_amount, status,
                 payment_state, shipping_address_json, items, created_at)
            VALUES (?, ?, ?, ?, 'pending', 'PENDING', ?, ?, ?)
            """,
            (
                session["user_id"], order_number, order_number, float(total),
                json.dumps(dict(address)), json.dumps(items), now_iso(),
            ),
        )
        conn.commit()
        conn.close()
        response = requests.post(
            f"{api_base}/orders",
            json={
                "order_id": order_number,
                "order_amount": float(total),
                "order_currency": "INR",
                "customer_details": {
                    "customer_id": f"user_{session['user_id']}",
                    "customer_name": address["name"],
                    "customer_email": address["email"],
                    "customer_phone": re.sub(r"\D", "", address["phone"] or ""),
                },
                "order_meta": {"return_url": return_url},
            },
            headers=cashfree_api_headers(credentials),
            timeout=20,
        )
        response.raise_for_status()
        payment_data = response.json()
        if not isinstance(payment_data, dict):
            raise ValueError("Cashfree payment response was invalid.")
        payment_session_id = payment_data.get("payment_session_id")
        if payment_data.get("order_id") != order_number or not isinstance(payment_session_id, str) or not payment_session_id:
            raise ValueError("Cashfree did not return a valid payment session.")

        conn = get_connection()
        conn.execute(
            "UPDATE orders SET cashfree_order_id = ? WHERE order_number = ? AND user_id = ?",
            (payment_data["order_id"], order_number, session["user_id"]),
        )
        conn.commit()
        conn.close()
        return jsonify({
            "merchant_order_id": order_number,
            "payment_session_id": payment_session_id,
            "cashfree_mode": environment,
        })
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except ValueError as error:
        if "order_number" not in locals():
            return jsonify({"error": str(error)}), 400
        app.logger.exception("Cashfree payment initiation failed")
        conn = get_connection()
        conn.execute(
            "UPDATE orders SET status = 'payment_failed', payment_state = 'FAILED' "
            "WHERE order_number = ? AND user_id = ? AND payment_state = 'PENDING'",
            (order_number, session["user_id"]),
        )
        conn.commit()
        conn.close()
        return jsonify({"error": "We could not start Cashfree checkout. Please try again."}), 502
    except requests.RequestException as error:
        details = cashfree_error_details(error)
        if details:
            app.logger.error("Cashfree order API rejected request: %s", details)
        app.logger.exception("Cashfree payment initiation failed")
        if "order_number" in locals():
            conn = get_connection()
            conn.execute(
                "UPDATE orders SET status = 'payment_failed', payment_state = 'FAILED' "
                "WHERE order_number = ? AND user_id = ? AND payment_state = 'PENDING'",
                (order_number, session["user_id"]),
            )
            conn.commit()
            conn.close()
        return jsonify({"error": "We could not start Cashfree checkout. Please try again."}), 502


def record_order_sales(conn, order_id):
    """Import paid order snapshots once; never infer a sale from a pending payment."""
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or order["payment_state"] != "COMPLETED":
        return 0
    items = json.loads(order["items"])
    if not isinstance(items, list) or not items:
        raise ValueError("Completed order has no valid items.")
    address = json.loads(order["shipping_address_json"] or "{}")
    if not isinstance(address, dict):
        raise ValueError("Completed order has an invalid address snapshot.")
    user = conn.execute("SELECT name FROM users WHERE id = ?", (order["user_id"],)).fetchone()
    customer = address.get("name") or (user["name"] if user else "")
    validated = []
    total = Decimal("0")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("Completed order has an invalid item snapshot.")
        quantity = item.get("qty")
        price = Decimal(str(item.get("unit_price", item.get("price"))))
        if (isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1
                or not price.is_finite() or price <= 0):
            raise ValueError("Completed order has an invalid quantity or recorded price.")
        product = conn.execute("SELECT id, name FROM products WHERE id = ?",
                               (item.get("product_id"),)).fetchone()
        # Use stored order details when a historical product was deleted or had no ID.
        name = item.get("name") or (product["name"] if product else None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Completed order has no product name snapshot.")
        validated.append((product["id"] if product else None, quantity, float(price),
                          customer, order["created_at"], order_id, index, name))
        total += price * quantity
    recorded_total = Decimal(str(order["total_amount"]))
    if (not recorded_total.is_finite()
            or total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != recorded_total):
        raise ValueError("Completed order item amounts do not match the paid total.")
    count = 0
    for values in validated:
        cursor = conn.execute(
            "INSERT INTO sales "
            "(product_id, quantity, selling_price, customer, date, order_id, order_item_index, product_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(order_id, order_item_index) DO NOTHING", values,
        )
        count += cursor.rowcount
    return count


def synchronize_completed_order_sales():
    conn = get_connection()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            orders = conn.execute("SELECT id FROM orders WHERE payment_state = 'COMPLETED'").fetchall()
            for order in orders:
                conn.execute("SAVEPOINT order_sales_import")
                try:
                    record_order_sales(conn, order["id"])
                except (ValueError, TypeError, InvalidOperation, sqlite3.IntegrityError):
                    conn.execute("ROLLBACK TO order_sales_import")
                    app.logger.warning("Skipped sales import for order id %s: invalid snapshot",
                                       order["id"])
                finally:
                    conn.execute("RELEASE order_sales_import")
    except sqlite3.Error:
        app.logger.exception("Completed order sales import unavailable; startup will continue")
    finally:
        conn.close()


synchronize_completed_order_sales()


@app.route("/api/payments/cashfree/<merchant_order_id>/status")
def cashfree_payment_status(merchant_order_id):
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
        conn = get_connection()
        try:
            with conn:
                record_order_sales(conn, order["id"])
        except (ValueError, TypeError, InvalidOperation, sqlite3.Error):
            app.logger.warning("Sales import unavailable for completed order id %s", order["id"])
        finally:
            conn.close()
        return jsonify({"order_number": merchant_order_id, "state": "COMPLETED"})

    try:
        api_base, credentials, _ = get_cashfree_settings()
        response = requests.get(
            f"{api_base}/orders/{merchant_order_id}",
            headers=cashfree_api_headers(credentials),
            timeout=15,
        )
        response.raise_for_status()
        payment_data = response.json()
        if not isinstance(payment_data, dict):
            raise ValueError("Cashfree order status response was invalid.")
        cashfree_status = payment_data.get("order_status")
        if payment_data.get("order_id") != merchant_order_id or cashfree_status not in {
            "ACTIVE", "PAID", "EXPIRED", "TERMINATED",
        }:
            raise ValueError("Cashfree returned an unrecognized order.")
        if cashfree_status == "PAID":
            try:
                paid_amount = Decimal(str(payment_data.get("order_amount")))
            except InvalidOperation as error:
                raise ValueError("Cashfree returned an invalid order amount.") from error
            if (
                not paid_amount.is_finite()
                or payment_data.get("order_currency") != "INR"
                or paid_amount != Decimal(str(order["total_amount"]))
            ):
                app.logger.error("Cashfree amount mismatch for order %s", merchant_order_id)
                return jsonify({"error": "Payment verification failed. Contact support."}), 502

        payment_state = {
            "PAID": "COMPLETED",
            "ACTIVE": "PENDING",
            "EXPIRED": "FAILED",
            "TERMINATED": "FAILED",
        }[cashfree_status]
        order_status = {
            "COMPLETED": "confirmed",
            "FAILED": "payment_failed",
            "PENDING": "pending",
        }[payment_state]
        conn = get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE orders
                    SET payment_state = ?, status = ?, cashfree_order_id = ?
                    WHERE id = ? AND user_id = ? AND payment_state != 'COMPLETED'
                    """,
                    (payment_state, order_status, merchant_order_id, order["id"], session["user_id"]),
                )
                if payment_state == "COMPLETED":
                    record_order_sales(conn, order["id"])
                    conn.execute("DELETE FROM user_carts WHERE user_id = ?", (session["user_id"],))
                stored_state = conn.execute(
                    "SELECT payment_state FROM orders WHERE id = ? AND user_id = ?",
                    (order["id"], session["user_id"]),
                ).fetchone()["payment_state"]
        finally:
            conn.close()
        return jsonify({"order_number": merchant_order_id, "state": stored_state})
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except (requests.RequestException, ValueError, InvalidOperation):
        app.logger.exception("Cashfree status verification failed for order %s", merchant_order_id)
        return jsonify({"error": "We could not verify this payment yet. Please try again."}), 502


@app.route("/shop/payment/cashfree/return")
def cashfree_payment_return():
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
        SELECT sales.*, COALESCE(sales.product_name, products.name) AS display_product_name
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
            "product_name": s["display_product_name"] or "—",
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
        SELECT sales.*, COALESCE(sales.product_name, products.name) AS display_product_name, orders.order_number
        FROM sales
        LEFT JOIN products ON sales.product_id = products.id
        LEFT JOIN orders ON sales.order_id = orders.id
        ORDER BY sales.date DESC
        """
    ).fetchall()
    conn.close()

    all_sales = [
        {
            "date": parse_date(r["date"]),
            "product_name": r["display_product_name"] or "—",
            "quantity": r["quantity"],
            "selling_price": r["selling_price"],
            "total_amount": round(r["quantity"] * r["selling_price"], 2),
            "customer": r["customer"],
            "order_number": r["order_number"],
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
    html_path = os.path.join(app.static_folder, "storefront", "shipping.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return inject_google_client_id(f.read())


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
    return redirect(url_for("shipping"))


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
