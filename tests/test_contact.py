from email.message import EmailMessage
import ssl

from app import app


def test_contact_page_has_a_form_and_existing_newsletter():
    response = app.test_client().get("/shop/contact")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="contact-form"' in html
    assert 'id="newsletter-signup"' in html
    assert 'href="mailto:thugile.official@gmail.com"' in html


def test_contact_message_is_sent_to_configured_inbox(monkeypatch):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example.com", 587, 15)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def ehlo(self):
            pass

        def starttls(self, context):
            pass

        def login(self, username, password):
            assert (username, password) == ("sender@example.com", "app-password")

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("CONTACT_EMAIL", "thugile.official@gmail.com")
    monkeypatch.setattr("app.smtplib.SMTP", FakeSMTP)

    response = app.test_client().post(
        "/api/contact",
        json={
            "name": "A customer",
            "email": "customer@example.com",
            "topic": "Order or delivery",
            "message": "Could you help with my order?",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert isinstance(message, EmailMessage)
    assert message["To"] == "thugile.official@gmail.com"
    assert message["Reply-To"] == "customer@example.com"
    assert "Could you help with my order?" in message.get_content()


def test_contact_message_uses_implicit_tls_on_port_465(monkeypatch):
    sent_messages = []

    class FakeSMTPSSL:
        def __init__(self, host, port, timeout, context):
            assert (host, port, timeout) == ("smtp.gmail.com", 465, 15)
            assert isinstance(context, ssl.SSLContext)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def login(self, username, password):
            assert (username, password) == ("sender@example.com", "app-password")

        def send_message(self, message):
            sent_messages.append(message)

    def unexpected_starttls(*args, **kwargs):
        raise AssertionError("port 465 must use implicit TLS, not STARTTLS")

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setattr("app.smtplib.SMTP_SSL", FakeSMTPSSL)
    monkeypatch.setattr("app.smtplib.SMTP", unexpected_starttls)

    response = app.test_client().post(
        "/api/contact",
        json={
            "name": "A customer",
            "email": "customer@example.com",
            "message": "Hello",
        },
    )

    assert response.status_code == 200
    assert len(sent_messages) == 1


def test_contact_message_rejects_non_string_input():
    response = app.test_client().post(
        "/api/contact",
        json={
            "name": 12,
            "email": "customer@example.com",
            "message": "Hello",
        },
    )

    assert response.status_code == 400


def test_contact_honeypot_does_not_send_email(monkeypatch):
    def unexpected_smtp(*args, **kwargs):
        raise AssertionError("honeypot submission must not send email")

    monkeypatch.setattr("app.smtplib.SMTP", unexpected_smtp)

    response = app.test_client().post(
        "/api/contact",
        json={
            "name": "A bot",
            "email": "bot@example.com",
            "message": "Spam",
            "website": "https://spam.example",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_contact_message_reports_missing_smtp_credentials(monkeypatch):
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    response = app.test_client().post(
        "/api/contact",
        json={
            "name": "A customer",
            "email": "customer@example.com",
            "message": "Hello",
        },
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.get_json()["error"]
