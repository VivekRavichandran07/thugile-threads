from datetime import datetime, timezone
import hashlib
import re

import pytest
from werkzeug.security import check_password_hash

import db
from app import app


@pytest.fixture
def security_client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "security-test.db"))
    db.init_db()
    conn = db.get_connection()
    user_id = conn.execute(
        """
        INSERT INTO users (name, email, password_hash, created_at)
        VALUES (?, ?, ?, ?)
        """,
        ("Test Customer", "customer@example.com", "old-password-hash", "2026-01-01"),
    ).lastrowid
    conn.commit()
    conn.close()
    return app.test_client(), user_id


def test_forgot_password_emails_a_hashed_expiring_single_use_token(
    security_client, monkeypatch
):
    client, user_id = security_client
    messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout, context):
            assert (host, port, timeout) == ("smtp.example.com", 465, 15)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def login(self, username, password):
            assert (username, password) == ("sender@example.com", "app-password")

        def send_message(self, message):
            messages.append(message)

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setitem(app.config, "PUBLIC_BASE_URL", "https://shop.example")
    monkeypatch.setattr("app.smtplib.SMTP_SSL", FakeSMTP)

    response = client.post(
        "/api/auth/forgot-password", json={"email": "customer@example.com"}
    )

    assert response.status_code == 200
    assert "reset_link" not in response.get_json()
    assert "If an account exists" in response.get_json()["message"]
    assert len(messages) == 1
    email_body = messages[0].get_content()
    match = re.search(r"https://shop\.example/shop/reset-password\?token=([^\s]+)", email_body)
    assert match
    token = match.group(1)

    conn = db.get_connection()
    reset = conn.execute(
        "SELECT token, expires_at, used FROM password_resets WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    assert reset["token"] == hashlib.sha256(token.encode()).hexdigest()
    assert reset["token"] != token
    assert datetime.fromisoformat(reset["expires_at"]) > datetime.now(timezone.utc).replace(tzinfo=None)
    assert reset["used"] == 0

    reset_response = client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "new-password"},
    )
    assert reset_response.status_code == 200
    repeated_response = client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "another-password"},
    )
    assert repeated_response.status_code == 400

    conn = db.get_connection()
    password_hash = conn.execute(
        "SELECT password_hash FROM users WHERE id = ?", (user_id,)
    ).fetchone()["password_hash"]
    conn.close()
    assert check_password_hash(password_hash, "new-password")


def test_forgot_password_does_not_disclose_unknown_accounts(security_client):
    client, _ = security_client

    existing = client.post(
        "/api/auth/forgot-password", json={"email": "customer@example.com"}
    )
    unknown = client.post(
        "/api/auth/forgot-password", json={"email": "missing@example.com"}
    )

    assert existing.status_code == unknown.status_code == 200
    assert existing.get_json() == unknown.get_json()
    assert "reset_link" not in existing.get_json()


def test_mutating_requests_require_a_csrf_token(security_client):
    client, _ = security_client
    page = client.get("/")
    token = page.headers["X-CSRF-Token"]
    html = page.get_data(as_text=True)

    assert f'name="csrf-token" content="{token}"' in html
    rejected = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "wrong"},
        headers={"X-CSRFToken": ""},
    )
    accepted = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "wrong"},
        headers={"X-CSRFToken": token},
    )

    assert rejected.status_code == 400
    assert accepted.status_code == 401


def test_login_attempts_are_rate_limited(security_client):
    client, _ = security_client
    client.get("/")

    responses = [
        client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "wrong"},
        )
        for _ in range(11)
    ]

    assert all(response.status_code == 401 for response in responses[:10])
    assert responses[-1].status_code == 429
    assert int(responses[-1].headers["Retry-After"]) > 0


def test_session_cookie_flags_are_hardened(security_client, monkeypatch):
    client, _ = security_client
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", True)

    response = client.get("/")
    cookie = response.headers["Set-Cookie"].lower()

    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
