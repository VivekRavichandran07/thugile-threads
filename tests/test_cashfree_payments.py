import base64
import hmac
import json
import os
import sqlite3
from datetime import datetime
from decimal import Decimal

import pytest

import db
import app as app_module
from app import app
from shipping import shipping_charge


@pytest.mark.parametrize(("month", "code"), tuple(enumerate((
    "PONGJAN10", "THAIFEB10", "PANGMAR10", "PUTHAPR10",
    "CHITMAY10", "VAIKJUN10", "AADIJUL10", "POOJAUG10",
    "NAVASEP10", "DEEPOCT10", "KARTNOV10", "VAIKDEC10",
), start=1)))
def test_monthly_discount_code(month, code, monkeypatch):
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz):
            return cls(2026, month, 1, tzinfo=tz)

    monkeypatch.setattr(app_module, "datetime", FixedClock)
    assert app_module.monthly_discount_code() == code


@pytest.mark.parametrize(("pin", "count", "subtotal", "charge"), [
    ("635109", 1, "1499", 47),
    ("635109", 3, "4497", 83),
    ("600001", 2, "2998", 89),
    ("641001", 3, "4598.99", 112),
    ("641001", 3, "4599", 0),
    ("500001", 4, "4000", 159),
    ("560001", 1, "1499", 89),
    ("682001", 5, "4000", 280),
    ("744101", 1, "1499", 106),
])
def test_shipping_rates(pin, count, subtotal, charge):
    assert shipping_charge(pin, count, Decimal(subtotal)) == charge


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise app_module.requests.HTTPError(response=self)

    def json(self):
        return self.payload


@pytest.fixture
def cashfree_client(tmp_path, monkeypatch):
    database_path = tmp_path / "cashfree-test.db"
    monkeypatch.setattr(db, "DB_PATH", str(database_path))
    db.init_db()

    conn = db.get_connection()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Test Customer", "payment-test@example.com", "", "2026-01-01T00:00:00"),
    )
    user_id = cursor.lastrowid
    conn.execute(
        """
        INSERT INTO user_addresses
            (user_id, name, email, phone, address, address_line_2, city, pincode, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            "Test Customer",
            "payment-test@example.com",
            "9876543210",
            "1 Test Street",
            "",
            "Chennai",
            "600001",
            "2026-01-01T00:00:00",
        ),
    )
    product_id = conn.execute(
        """
        INSERT INTO products (name, sku, size, selling_price, discounted_price, quantity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("Test Kurta", "payment-test-kurta", "M", 100, 75, 2, "2026-01-01T00:00:00"),
    ).lastrowid
    conn.commit()
    conn.close()

    monkeypatch.setenv("CASHFREE_APP_ID", "test-app")
    monkeypatch.setenv("CASHFREE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CASHFREE_ENV", "sandbox")
    monkeypatch.setenv("CASHFREE_REDIRECT_BASE_URL", "https://shop.example")
    monkeypatch.setattr(app_module, "send_storefront_email", lambda message, **kwargs: None)

    client = app.test_client()
    client.product_id = product_id
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return client, database_path


def test_cashfree_checkout_uses_server_prices_and_confirms_only_verified_payment(
    cashfree_client, monkeypatch
):
    client, database_path = cashfree_client
    payment_request = {}

    def fake_post(url, **kwargs):
        payment_request["url"] = url
        payment_request.update(kwargs["json"])
        payment_request["headers"] = kwargs["headers"]
        return FakeResponse({
            "order_id": kwargs["json"]["order_id"],
            "order_status": "ACTIVE",
            "payment_session_id": "cashfree-session-123",
        })

    monkeypatch.setattr("app.requests.post", fake_post)
    items = [{"product_id": client.product_id, "qty": 1, "price": 1}]
    quote = client.post("/api/store/checkout/quote", json={"address_id": 1, "items": items})
    assert quote.json == {"merchandise": 75, "shipping": 65, "total": 140}
    stale = client.post("/api/payments/cashfree", json={
        "address_id": 1, "items": items, "quoted_total": 75,
    })
    assert stale.status_code == 400
    assert not payment_request
    response = client.post(
        "/api/payments/cashfree",
        json={
            "address_id": 1,
            "total": 1,
            "items": items,
            "quoted_total": quote.json["total"],
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert payment_request["url"] == "https://sandbox.cashfree.com/pg/orders"
    assert payment_request["order_amount"] == 140
    assert payment_request["order_currency"] == "INR"
    assert payment_request["customer_details"]["customer_phone"] == "9876543210"
    assert payment_request["order_meta"]["return_url"].startswith(
        "https://shop.example/shop/payment/cashfree/return?order_id="
    )
    assert payment_request["order_meta"]["notify_url"] == "https://shop.example/api/payments/cashfree/webhook"
    assert payment_request["headers"]["x-client-id"] == "test-app"
    assert payment_request["headers"]["x-client-secret"] == "test-secret"
    assert data["payment_session_id"] == "cashfree-session-123"

    monkeypatch.setattr(
        "app.requests.get",
        lambda *args, **kwargs: FakeResponse({
            "order_id": data["merchant_order_id"],
            "order_status": "PAID",
            "order_amount": 140,
            "order_currency": "INR",
        }),
    )
    status = client.get(
        f"/api/payments/cashfree/{data['merchant_order_id']}/status"
    )
    assert status.status_code == 200
    assert status.get_json()["state"] == "COMPLETED"

    conn = sqlite3.connect(database_path)
    order = conn.execute(
        "SELECT total_amount, status, payment_state, cashfree_order_id, shipping_charge FROM orders"
    ).fetchone()
    conn.close()
    assert order == (140.0, "confirmed", "COMPLETED", data["merchant_order_id"], 65)
    repeated = client.get(f"/api/payments/cashfree/{data['merchant_order_id']}/status")
    assert repeated.status_code == 200
    conn = sqlite3.connect(database_path)
    assert conn.execute("SELECT quantity, selling_price, product_name FROM sales").fetchall() == [(1, 75, "Test Kurta")]
    conn.close()


def test_paid_webhook_sends_separate_order_emails_and_retries_only_failed_copy(cashfree_client, monkeypatch):
    client, database_path = cashfree_client
    monkeypatch.setattr(app_module.requests, "post", lambda url, **kwargs: FakeResponse({
        "order_id": kwargs["json"]["order_id"], "payment_session_id": "webhook-session",
    }))
    response = client.post("/api/payments/cashfree", json={
        "address_id": 1, "items": [{"product_id": client.product_id, "qty": 1}],
    })
    order_id = response.json["merchant_order_id"]
    monkeypatch.setattr(app_module.requests, "get", lambda *args, **kwargs: FakeResponse({
        "order_id": order_id, "order_status": "PAID", "order_amount": 140, "order_currency": "INR",
    }))
    delivered = []
    attempts = []

    def send(message, **kwargs):
        recipient = str(message["To"])
        attempts.append(recipient)
        if len(attempts) == 1:
            raise OSError("Temporary SMTP failure")
        delivered.append((recipient, message.get_content()))

    monkeypatch.setattr(app_module, "send_storefront_email", send)
    body = json.dumps({"type": "PAYMENT_SUCCESS_WEBHOOK", "data": {"order": {"order_id": order_id}}})
    timestamp = "1795622400000"
    signature = base64.b64encode(hmac.digest(b"test-secret", (timestamp + body).encode(), "sha256")).decode()
    webhook = app.test_client()
    headers = {"x-webhook-timestamp": timestamp, "x-webhook-signature": signature}
    endpoint = "/api/payments/cashfree/webhook"
    assert webhook.post(endpoint, data=body + " ", content_type="application/json", headers=headers).status_code == 401
    assert webhook.post(endpoint, data=body, content_type="application/json", headers=headers).status_code == 503
    assert webhook.post(endpoint, data=body, content_type="application/json", headers=headers).status_code == 200
    assert webhook.post(endpoint, data=body, content_type="application/json", headers=headers).status_code == 200
    assert attempts == ["payment-test@example.com", "thugile.official@gmail.com", "payment-test@example.com"]
    for _, content in delivered:
        for detail in (order_id, "Test Kurta", "payment-test-kurta", "M", "1 Test Street",
                       "9876543210", "Shipping: ₹65.00", "Total paid: ₹140.00"):
            assert detail in content
    with sqlite3.connect(database_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone() == (1,)
        assert conn.execute("SELECT quantity FROM products WHERE id = ?", (client.product_id,)).fetchone() == (1,)



def test_cashfree_checkout_rejects_client_controlled_stock_and_prices(cashfree_client):
    client, _ = cashfree_client

    response = client.post(
        "/api/payments/cashfree",
        json={
            "address_id": 1,
            "items": [
                {"product_id": client.product_id, "qty": 2, "price": 0.01},
                {"product_id": client.product_id, "qty": 2, "price": 0.01},
            ],
        },
    )

    assert response.status_code == 400
    assert "no longer available" in response.get_json()["error"]


def test_cashfree_status_does_not_confirm_amount_or_currency_mismatch(
    cashfree_client, monkeypatch
):
    client, database_path = cashfree_client
    monkeypatch.setattr(
        "app.requests.post",
        lambda url, **kwargs: FakeResponse({
            "order_id": kwargs["json"]["order_id"],
            "payment_session_id": "cashfree-session-456",
        }),
    )
    created = client.post(
        "/api/payments/cashfree",
        json={"address_id": 1, "items": [{"product_id": client.product_id, "qty": 1}]},
    ).get_json()
    monkeypatch.setattr(
        "app.requests.get",
        lambda *args, **kwargs: FakeResponse({
            "order_id": created["merchant_order_id"],
            "order_status": "PAID",
            "order_amount": 1,
            "order_currency": "USD",
        }),
    )

    response = client.get(
        f"/api/payments/cashfree/{created['merchant_order_id']}/status"
    )

    assert response.status_code == 502
    conn = sqlite3.connect(database_path)
    state = conn.execute("SELECT status, payment_state FROM orders").fetchone()
    conn.close()
    assert state == ("pending", "PENDING")


def test_production_uses_cashfree_production_api(monkeypatch):
    monkeypatch.setenv("CASHFREE_APP_ID", "test-app")
    monkeypatch.setenv("CASHFREE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CASHFREE_ENV", "production")
    monkeypatch.setenv("CASHFREE_REDIRECT_BASE_URL", "https://shop.example")

    api_base, credentials, environment = app_module.get_cashfree_settings()

    assert api_base == "https://api.cashfree.com/pg"
    assert credentials == {"client_id": "test-app", "client_secret": "test-secret"}
    assert environment == "production"


def test_env_file_loader_supports_quotes_comments_and_existing_environment(
    tmp_path, monkeypatch
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'export CASHFREE_APP_ID = "sandbox-app"\n'
        "CASHFREE_SECRET_KEY=secret#fragment\n"
        "CASHFREE_ENV=production\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CASHFREE_ENV", "sandbox")
    monkeypatch.delenv("CASHFREE_APP_ID", raising=False)
    monkeypatch.delenv("CASHFREE_SECRET_KEY", raising=False)

    app_module.load_env_file(str(env_file))

    assert os.environ["CASHFREE_APP_ID"] == "sandbox-app"
    assert os.environ["CASHFREE_SECRET_KEY"] == "secret#fragment"
    assert os.environ["CASHFREE_ENV"] == "sandbox"


def test_checkout_uses_cashfree_hosted_checkout():
    response = app.test_client().get("/shop/checkout")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="payment"' not in page
    assert "Continue to Pay" in page
    assert "https://sdk.cashfree.com/js/v3/cashfree.js" in page
    assert "phonepe" not in page.lower()


def test_cashfree_checkout_reports_missing_server_credentials(cashfree_client, monkeypatch):
    client, _ = cashfree_client
    monkeypatch.delenv("CASHFREE_SECRET_KEY")

    response = client.post(
        "/api/payments/cashfree",
        json={"address_id": 1, "items": [{"product_id": client.product_id, "qty": 1}]},
    )

    assert response.status_code == 503
    assert "CASHFREE_APP_ID and CASHFREE_SECRET_KEY" in response.get_json()["error"]


def test_cashfree_order_creation_failure_does_not_leave_pending_order(
    cashfree_client, monkeypatch, caplog
):
    client, database_path = cashfree_client
    monkeypatch.setattr(
        "app.requests.post",
        lambda *args, **kwargs: FakeResponse(
            {
                "code": "invalid_request",
                "type": "invalid_request_error",
                "message": "customer_phone must contain 10 digits",
            },
            status_code=400,
        ),
    )

    response = client.post(
        "/api/payments/cashfree",
        json={
            "address_id": 1,
            "items": [{"product_id": client.product_id, "qty": 1}],
        },
    )

    assert response.status_code == 502
    conn = sqlite3.connect(database_path)
    state = conn.execute("SELECT status, payment_state FROM orders").fetchone()
    conn.close()
    assert state == ("payment_failed", "FAILED")
    assert "customer_phone must contain 10 digits" in caplog.text
    assert "invalid_request" in caplog.text


def test_monthly_discount_is_applied_to_payment_and_sale(cashfree_client, monkeypatch):
    client, database_path = cashfree_client
    monkeypatch.setattr(app_module, "monthly_discount_code", lambda: "DEEPOCT10")
    charged = {}
    def fake_post(url, **kwargs):
        charged.update(kwargs["json"])
        return FakeResponse({"order_id": charged["order_id"], "payment_session_id": "discount-session"})
    monkeypatch.setattr(app_module.requests, "post", fake_post)
    payload = {"code": " deepoct10 ", "items": [{"product_id": client.product_id, "qty": 2}]}
    preview = client.post("/api/store/discount/validate", json=payload)
    assert preview.status_code == 200
    assert preview.json["total"] == 135
    assert preview.json["discount"] == 15
    response = client.post("/api/payments/cashfree", json={
        "address_id": 1, "discount_code": "DEEPOCT10", "items": payload["items"], "total": 1,
    })
    assert response.status_code == 200
    assert charged["order_amount"] == 224
    # A pending discounted payment reserves eligibility, including simultaneous retries.
    assert client.post("/api/store/discount/validate", json=payload).status_code == 400
    monkeypatch.setattr(app_module.requests, "get", lambda *args, **kwargs: FakeResponse({
        "order_id": response.json["merchant_order_id"], "order_status": "PAID",
        "order_amount": 224, "order_currency": "INR",
    }))
    assert client.get(f"/api/payments/cashfree/{response.json['merchant_order_id']}/status").status_code == 200
    with sqlite3.connect(database_path) as conn:
        assert conn.execute(
            "SELECT total_amount, discount_code, discount_amount, shipping_charge FROM orders"
        ).fetchone() == (224, "DEEPOCT10", 15, 89)
        assert conn.execute("SELECT quantity, selling_price FROM sales").fetchone() == (2, 67.5)
    assert client.post("/api/store/discount/validate", json=payload).status_code == 400


def test_checkout_quote_applies_free_shipping_threshold_after_discount(cashfree_client, monkeypatch):
    client, database_path = cashfree_client
    monkeypatch.setattr(app_module, "monthly_discount_code", lambda: "DEEPOCT10")
    with sqlite3.connect(database_path) as conn:
        conn.execute("UPDATE products SET discounted_price = 4599 WHERE id = ?", (client.product_id,))
    payload = {"address_id": 1, "items": [{"product_id": client.product_id, "qty": 1}]}
    quote = client.post("/api/store/checkout/quote", json=payload)
    assert quote.json == {"merchandise": 4599, "shipping": 0, "total": 4599}
    quote = client.post("/api/store/checkout/quote", json={**payload, "discount_code": "DEEPOCT10"})
    assert quote.json == {"merchandise": 4139.1, "shipping": 65, "total": 4204.1}
    with sqlite3.connect(database_path) as conn:
        conn.execute("UPDATE user_addresses SET pincode = '000000'")
    assert client.post("/api/store/checkout/quote", json=payload).status_code == 400


def test_discount_rejects_wrong_month_and_existing_customers(cashfree_client, monkeypatch):
    client, database_path = cashfree_client
    monkeypatch.setattr(app_module, "monthly_discount_code", lambda: "DEEPOCT10")
    payload = {"code": "PANGMAR10", "items": [{"product_id": client.product_id, "qty": 1}]}
    assert client.post("/api/store/discount/validate", json=payload).status_code == 400
    payload["code"] = "OCT10"
    assert client.post("/api/store/discount/validate", json=payload).status_code == 400
    with sqlite3.connect(database_path) as conn:
        conn.execute("INSERT INTO orders (user_id, order_number, total_amount, status, payment_state, items, created_at) VALUES (1, 'previous', 75, 'confirmed', 'COMPLETED', '[]', '2026-01-01')")
    payload["code"] = "DEEPOCT10"
    assert client.post("/api/store/discount/validate", json=payload).status_code == 400
    assert client.post("/api/payments/cashfree", json={"address_id": 1, "discount_code": "DEEPOCT10", "items": payload["items"]}).status_code == 400


def test_discount_rounding_matches_paid_total_and_requires_login(cashfree_client, monkeypatch):
    client, database_path = cashfree_client
    monkeypatch.setattr(app_module, "monthly_discount_code", lambda: "DEEPOCT10")
    with sqlite3.connect(database_path) as conn:
        conn.execute("UPDATE products SET discounted_price = 75.05 WHERE id = ?", (client.product_id,))
    payload = {"code": "DEEPOCT10", "items": [{"product_id": client.product_id, "qty": 2}]}
    response = client.post("/api/store/discount/validate", json=payload)
    assert response.json["total"] == 135.09
    with client.session_transaction() as session:
        session.clear()
    assert client.post("/api/store/discount/validate", json=payload).status_code == 401


def test_offer_hides_for_any_order_history_and_is_not_cached(cashfree_client):
    client, database_path = cashfree_client
    response = client.get("/api/store/discount-offer")
    assert response.json == {"code": app_module.monthly_discount_code(), "eligible": True}
    assert response.headers["Cache-Control"] == "private, no-store"
    with sqlite3.connect(database_path) as conn:
        conn.execute("INSERT INTO orders (user_id, order_number, total_amount, status, payment_state, items, created_at) VALUES (1, 'past-attempt', 75, 'payment_failed', 'FAILED', '[]', '2026-01-01')")
    response = client.get("/api/store/discount-offer")
    assert response.json == {"code": None, "eligible": False}
    with client.session_transaction() as session:
        session.clear()
    assert client.get("/api/store/discount-offer").json == {"code": None, "eligible": True}
