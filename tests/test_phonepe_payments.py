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
        return None

    def json(self):
        return self.payload


@pytest.fixture
def phonepe_client(tmp_path, monkeypatch):
    database_path = tmp_path / "phonepe-test.db"
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

    monkeypatch.setenv("PHONEPE_CLIENT_ID", "test-client")
    monkeypatch.setenv("PHONEPE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("PHONEPE_CLIENT_VERSION", "1")
    monkeypatch.setenv("PHONEPE_ENV", "sandbox")
    monkeypatch.setenv("PHONEPE_REDIRECT_BASE_URL", "https://shop.example")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return client, database_path


def test_phonepe_checkout_uses_server_prices_and_confirms_only_verified_payment(
    phonepe_client, monkeypatch
):
    client, database_path = phonepe_client
    payment_request = {}

    def fake_post(url, **kwargs):
        if url.endswith("/v1/oauth/token"):
            return FakeResponse({"access_token": "test-access-token"})
        payment_request.update(kwargs["json"])
        payment_request["headers"] = kwargs["headers"]
        return FakeResponse({
            "orderId": "phonepe-order-123",
            "state": "PENDING",
            "redirectUrl": "https://mercury.phonepe.com/transact/test",
        })

    monkeypatch.setattr("app.requests.post", fake_post)
    response = client.post(
        "/api/payments/phonepe",
        json={
            "address_id": 1,
            "total": 1,
            "items": [{"name": "Test Kurta", "size": "M", "qty": 1, "price": 1}],
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert payment_request["amount"] == 7500
    assert payment_request["paymentFlow"]["merchantUrls"]["redirectUrl"].startswith(
        "https://shop.example/shop/payment/phonepe/return?"
    )
    assert payment_request["headers"]["Authorization"] == "O-Bearer test-access-token"

    monkeypatch.setattr(
        "app.requests.get",
        lambda *args, **kwargs: FakeResponse({
            "orderId": "phonepe-order-123",
            "state": "COMPLETED",
            "amount": 7500,
        }),
    )
    status = client.get(
        f"/api/payments/phonepe/{data['merchant_order_id']}/status"
    )
    assert status.status_code == 200
    assert status.get_json()["state"] == "COMPLETED"

    conn = sqlite3.connect(database_path)
    order = conn.execute(
        "SELECT total_amount, status, payment_state, phonepe_order_id FROM orders"
    ).fetchone()
    conn.close()
    assert order == (75.0, "confirmed", "COMPLETED", "phonepe-order-123")


def test_phonepe_checkout_rejects_client_controlled_stock_and_prices(phonepe_client):
    client, _ = phonepe_client

    response = client.post(
        "/api/payments/phonepe",
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


def test_phonepe_status_does_not_confirm_amount_mismatch(phonepe_client, monkeypatch):
    client, database_path = phonepe_client
    monkeypatch.setattr(
        "app.requests.post",
        lambda url, **kwargs: (
            FakeResponse({"access_token": "test-access-token"})
            if url.endswith("/v1/oauth/token")
            else FakeResponse({
                "orderId": "phonepe-order-456",
                "redirectUrl": "https://mercury.phonepe.com/transact/test",
            })
        ),
    )
    created = client.post(
        "/api/payments/phonepe",
        json={"address_id": 1, "items": [{"name": "Test Kurta", "size": "M", "qty": 1}]},
    ).get_json()
    monkeypatch.setattr(
        "app.requests.get",
        lambda *args, **kwargs: FakeResponse({"state": "COMPLETED", "amount": 1}),
    )

    response = client.get(
        f"/api/payments/phonepe/{created['merchant_order_id']}/status"
    )

    assert response.status_code == 502
    conn = sqlite3.connect(database_path)
    state = conn.execute("SELECT status, payment_state FROM orders").fetchone()
    conn.close()
    assert state == ("pending", "PENDING")


def test_production_uses_phonepe_identity_manager_for_oauth(monkeypatch):
    monkeypatch.setenv("PHONEPE_CLIENT_ID", "test-client")
    monkeypatch.setenv("PHONEPE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("PHONEPE_CLIENT_VERSION", "1")
    monkeypatch.setenv("PHONEPE_ENV", "production")
    monkeypatch.setenv("PHONEPE_REDIRECT_BASE_URL", "https://shop.example")

    api_base, token_url, _ = app_module.get_phonepe_settings()

    assert api_base == "https://api.phonepe.com/apis/pg"
    assert token_url == "https://api.phonepe.com/apis/identity-manager/v1/oauth/token"


def test_env_file_loader_supports_quotes_comments_and_existing_environment(
    tmp_path, monkeypatch
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'export PHONEPE_CLIENT_ID = "sandbox-client"\n'
        "PHONEPE_CLIENT_SECRET=secret#fragment\n"
        "PHONEPE_CLIENT_VERSION=1 # dashboard version\n"
        "PHONEPE_ENV=production\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PHONEPE_ENV", "sandbox")
    monkeypatch.delenv("PHONEPE_CLIENT_ID", raising=False)
    monkeypatch.delenv("PHONEPE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("PHONEPE_CLIENT_VERSION", raising=False)

    app_module.load_env_file(str(env_file))

    assert os.environ["PHONEPE_CLIENT_ID"] == "sandbox-client"
    assert os.environ["PHONEPE_CLIENT_SECRET"] == "secret#fragment"
    assert os.environ["PHONEPE_CLIENT_VERSION"] == "1"
    assert os.environ["PHONEPE_ENV"] == "sandbox"


def test_checkout_uses_phonepe_instead_of_placeholder_payment_options():
    response = app.test_client().get("/shop/checkout")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="payment"' not in page
    assert "Continue to PhonePe" in page
    assert "https://mercury.phonepe.com/web/bundle/checkout.js" in page


def test_phonepe_checkout_reports_missing_server_credentials(phonepe_client, monkeypatch):
    client, _ = phonepe_client
    monkeypatch.delenv("PHONEPE_CLIENT_SECRET")

    response = client.post(
        "/api/payments/phonepe",
        json={"address_id": 1, "items": [{"name": "Test Kurta", "size": "M", "qty": 1}]},
    )

    assert response.status_code == 503
    assert "PHONEPE_CLIENT_SECRET" in response.get_json()["error"]


def test_phonepe_oauth_401_reports_credential_problem_without_creating_order(
    phonepe_client, monkeypatch
):
    client, database_path = phonepe_client
    monkeypatch.setattr(
        "app.requests.post",
        lambda *args, **kwargs: FakeResponse(
            {"success": False, "code": "401"},
            status_code=401,
        ),
    )

    response = client.post(
        "/api/payments/phonepe",
        json={
            "address_id": 1,
            "items": [{"name": "Test Kurta", "size": "M", "qty": 1}],
        },
    )

    assert response.status_code == 502
    error = response.get_json()["error"]
    assert "matching Standard Checkout credential set" in error
    assert "test-secret" not in error
    conn = sqlite3.connect(database_path)
    order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    assert order_count == 0
