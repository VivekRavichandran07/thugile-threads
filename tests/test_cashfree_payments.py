import os
import sqlite3

import pytest

import db
import app as app_module
from app import app


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
    conn.execute(
        """
        INSERT INTO products (name, sku, size, selling_price, discounted_price, quantity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("Test Kurta", "payment-test-kurta", "M", 100, 75, 2, "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("CASHFREE_APP_ID", "test-app")
    monkeypatch.setenv("CASHFREE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CASHFREE_ENV", "sandbox")
    monkeypatch.setenv("CASHFREE_REDIRECT_BASE_URL", "https://shop.example")

    client = app.test_client()
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
    response = client.post(
        "/api/payments/cashfree",
        json={
            "address_id": 1,
            "total": 1,
            "items": [{"name": "Test Kurta", "size": "M", "qty": 1, "price": 1}],
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert payment_request["url"] == "https://sandbox.cashfree.com/pg/orders"
    assert payment_request["order_amount"] == 75
    assert payment_request["order_currency"] == "INR"
    assert payment_request["customer_details"]["customer_phone"] == "9876543210"
    assert payment_request["order_meta"]["return_url"].startswith(
        "https://shop.example/shop/payment/cashfree/return?order_id="
    )
    assert payment_request["headers"]["x-client-id"] == "test-app"
    assert payment_request["headers"]["x-client-secret"] == "test-secret"
    assert data["payment_session_id"] == "cashfree-session-123"

    monkeypatch.setattr(
        "app.requests.get",
        lambda *args, **kwargs: FakeResponse({
            "order_id": data["merchant_order_id"],
            "order_status": "PAID",
            "order_amount": 75,
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
        "SELECT total_amount, status, payment_state, cashfree_order_id FROM orders"
    ).fetchone()
    conn.close()
    assert order == (75.0, "confirmed", "COMPLETED", data["merchant_order_id"])


def test_cashfree_checkout_rejects_client_controlled_stock_and_prices(cashfree_client):
    client, _ = cashfree_client

    response = client.post(
        "/api/payments/cashfree",
        json={
            "address_id": 1,
            "items": [
                {"name": "Test Kurta", "size": "M", "qty": 2, "price": 0.01},
                {"name": "Test Kurta", "size": "M", "qty": 2, "price": 0.01},
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
        json={"address_id": 1, "items": [{"name": "Test Kurta", "size": "M", "qty": 1}]},
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
    assert "Continue to Cashfree" in page
    assert "https://sdk.cashfree.com/js/v3/cashfree.js" in page
    assert "phonepe" not in page.lower()


def test_cashfree_checkout_reports_missing_server_credentials(cashfree_client, monkeypatch):
    client, _ = cashfree_client
    monkeypatch.delenv("CASHFREE_SECRET_KEY")

    response = client.post(
        "/api/payments/cashfree",
        json={"address_id": 1, "items": [{"name": "Test Kurta", "size": "M", "qty": 1}]},
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
            "items": [{"name": "Test Kurta", "size": "M", "qty": 1}],
        },
    )

    assert response.status_code == 502
    conn = sqlite3.connect(database_path)
    state = conn.execute("SELECT status, payment_state FROM orders").fetchone()
    conn.close()
    assert state == ("payment_failed", "FAILED")
    assert "customer_phone must contain 10 digits" in caplog.text
    assert "invalid_request" in caplog.text
