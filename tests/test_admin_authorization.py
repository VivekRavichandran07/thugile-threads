import sqlite3

import db
import pytest
from app import app, synchronize_admin_accounts


@pytest.fixture
def admin_auth_client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "admin-auth-test.db"))
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    db.init_db()
    conn = db.get_connection()
    customer_id = conn.execute(
        """
        INSERT INTO users (name, email, password_hash, created_at)
        VALUES (?, ?, ?, ?)
        """,
        ("Customer", "customer@example.com", "", "2026-01-01T00:00:00"),
    ).lastrowid
    admin_id = conn.execute(
        """
        INSERT INTO users (name, email, password_hash, created_at, is_admin)
        VALUES (?, ?, ?, ?, 1)
        """,
        ("Admin", "admin@example.com", "", "2026-01-01T00:00:00"),
    ).lastrowid
    conn.execute(
        "INSERT INTO subscribers (email, subscribed_at) VALUES (?, ?)",
        ("subscriber@example.com", "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()
    return app.test_client(), customer_id, admin_id


def login_as(client, user_id):
    with client.session_transaction() as user_session:
        user_session["user_id"] = user_id


def test_every_admin_route_rejects_an_authenticated_customer(admin_auth_client):
    client, customer_id, _ = admin_auth_client
    login_as(client, customer_id)
    routes = (
        ("GET", "/admin/"),
        ("GET", "/admin/products"),
        ("GET", "/admin/products/add"),
        ("POST", "/admin/products/add"),
        ("GET", "/admin/products/1/edit"),
        ("POST", "/admin/products/1/edit"),
        ("POST", "/admin/products/1/delete"),
        ("GET", "/admin/purchases"),
        ("GET", "/admin/purchases/add"),
        ("POST", "/admin/purchases/add"),
        ("GET", "/admin/sales"),
        ("GET", "/admin/subscribers"),
        ("POST", "/admin/subscribers/delete"),
        ("GET", "/admin/sales/add"),
        ("POST", "/admin/sales/add"),
    )

    for method, path in routes:
        response = client.open(path, method=method)
        assert response.status_code == 403, f"{method} {path}"


def test_admin_role_can_access_admin_pages_and_subscriber_list(admin_auth_client):
    client, _, admin_id = admin_auth_client
    login_as(client, admin_id)

    assert client.get("/admin/products").status_code == 200
    add_product_page = client.get("/admin/products/add")
    csrf_token = add_product_page.headers["X-CSRF-Token"]
    assert f'name="csrf_token" value="{csrf_token}"' in add_product_page.get_data(as_text=True)
    response = client.get("/api/newsletter/subscribers")
    assert response.status_code == 200
    assert response.get_json() == {
        "subscribers": [
            {
                "email": "subscriber@example.com",
                "subscribed_at": "2026-01-01T00:00:00",
            }
        ]
    }


def test_newsletter_subscriber_list_rejects_customers_and_guests(admin_auth_client):
    client, customer_id, _ = admin_auth_client
    login_as(client, customer_id)
    customer_response = client.get("/api/newsletter/subscribers")
    assert customer_response.status_code == 403

    with client.session_transaction() as user_session:
        user_session.clear()
    guest_response = client.get("/api/newsletter/subscribers")
    assert guest_response.status_code == 401


def test_newly_registered_customer_does_not_get_admin_access(
    admin_auth_client, monkeypatch
):
    client, _, _ = admin_auth_client
    response = client.post(
        "/api/auth/register",
        json={
            "name": "New customer",
            "email": "new-customer@example.com",
            "password": "customer-password",
        },
    )

    assert response.status_code == 200
    assert client.get("/admin/").status_code == 403


def test_admin_roles_are_synchronized_from_configured_email_allowlist(
    admin_auth_client, monkeypatch
):
    _, _, admin_id = admin_auth_client
    monkeypatch.setenv("ADMIN_EMAILS", " ADMIN@example.com ")

    synchronize_admin_accounts()

    conn = db.get_connection()
    admin_role = conn.execute(
        "SELECT is_admin FROM users WHERE id = ?", (admin_id,)
    ).fetchone()["is_admin"]
    customer_role = conn.execute(
        "SELECT is_admin FROM users WHERE email = ?",
        ("customer@example.com",),
    ).fetchone()["is_admin"]
    conn.close()

    assert admin_role == 1
    assert customer_role == 0


def test_empty_admin_allowlist_revokes_all_admin_roles(
    admin_auth_client, monkeypatch
):
    monkeypatch.setenv("ADMIN_EMAILS", "")

    synchronize_admin_accounts()

    conn = db.get_connection()
    admin_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE is_admin = 1"
    ).fetchone()[0]
    conn.close()

    assert admin_count == 0


def test_user_schema_defaults_new_accounts_to_non_admin(admin_auth_client):
    conn = db.get_connection()
    customer_role = conn.execute(
        "SELECT is_admin FROM users WHERE email = ?",
        ("customer@example.com",),
    ).fetchone()["is_admin"]
    conn.close()

    assert customer_role == 0


def test_existing_user_table_migrates_with_admin_disabled_by_default(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "legacy-users.db"
    conn = sqlite3.connect(database_path)
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Legacy customer", "legacy@example.com", "", "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(database_path))

    db.init_db()

    conn = db.get_connection()
    migrated_role = conn.execute(
        "SELECT is_admin FROM users WHERE email = ?", ("legacy@example.com",)
    ).fetchone()["is_admin"]
    conn.close()
    assert migrated_role == 0
