import smtplib

from app import app
from db import get_connection, now_iso


def setup_request():
    conn = get_connection()
    user_id = conn.execute(
        "INSERT INTO users (name,email,password_hash,created_at,phone) VALUES (?,?,?,?,?)",
        ("Customer", "customer@example.com", "unused", now_iso(), "9876543210"),
    ).lastrowid
    product_id = conn.execute(
        "INSERT INTO products (name,sku,color,quantity,created_at) VALUES (?,?,?,?,?)",
        ("Kurta", "RESTOCK-1", "Blue", 0, now_iso()),
    ).lastrowid
    conn.commit()
    conn.close()
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return client, product_id


def test_restock_requires_login():
    assert app.test_client().post('/api/store/restock', json={"product_id": 1}).status_code == 401


def test_restock_sends_account_and_product_details(monkeypatch):
    client, product_id = setup_request()
    messages = []
    monkeypatch.setattr('app.send_storefront_email', messages.append)
    monkeypatch.delenv('CONTACT_EMAIL', raising=False)
    response = client.post('/api/store/restock', json={"product_id": product_id, "email": "spoof@example.com"})
    assert response.status_code == 200
    assert messages[0]['To'] == 'thugile.official@gmail.com'
    assert messages[0]['Reply-To'] == 'customer@example.com'
    body = messages[0].get_content()
    assert 'Kurta' in body and 'Blue' in body and '9876543210' in body
    assert 'spoof@example.com' not in body


def test_restock_rejects_available_and_missing_products(monkeypatch):
    client, product_id = setup_request()
    monkeypatch.setattr('app.send_storefront_email', lambda message: (_ for _ in ()).throw(AssertionError('Unexpected email')))
    assert client.post('/api/store/restock', json={"product_id": 999999}).status_code == 404
    assert client.post('/api/store/restock', json={"product_id": "invalid"}).status_code == 400
    conn = get_connection()
    conn.execute('UPDATE products SET quantity = 1 WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    assert client.post('/api/store/restock', json={"product_id": product_id}).status_code == 409


def test_restock_reports_delivery_failure(monkeypatch):
    client, product_id = setup_request()
    def fail(message):
        raise smtplib.SMTPException('Unavailable')
    monkeypatch.setattr('app.send_storefront_email', fail)
    assert client.post('/api/store/restock', json={"product_id": product_id}).status_code == 503
