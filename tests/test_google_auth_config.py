from app import app

DEFAULT_CLIENT_ID = "296701170942-b4p3gv5us65uape6unq1jtqhsbljdutf.apps.googleusercontent.com"


def test_google_auth_config_returns_configured_client_id(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")

    response = app.test_client().get("/api/auth/google/config")

    assert response.status_code == 200
    assert response.get_json() == {
        "client_id": "test-client-id.apps.googleusercontent.com"
    }


def test_google_auth_config_uses_default_when_client_id_is_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    response = app.test_client().get("/api/auth/google/config")

    assert response.status_code == 200
    assert response.get_json() == {"client_id": DEFAULT_CLIENT_ID}


def test_google_auth_config_uses_default_when_client_id_is_empty(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "  ")

    response = app.test_client().get("/api/auth/google/config")

    assert response.status_code == 200
    assert response.get_json() == {"client_id": DEFAULT_CLIENT_ID}


def test_storefront_embeds_default_client_id_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    response = app.test_client().get("/shop/")

    assert response.status_code == 200
    assert 'data-client_id=""' not in response.get_data(as_text=True)
    assert f'data-client_id="{DEFAULT_CLIENT_ID}"' in response.get_data(as_text=True)


def test_storefront_embeds_configured_client_id(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "custom-client-id.apps.googleusercontent.com")

    response = app.test_client().get("/shop/")

    assert response.status_code == 200
    assert 'data-client_id="custom-client-id.apps.googleusercontent.com"' in response.get_data(as_text=True)


def test_google_signin_pages_embed_the_configured_client_id(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "custom-client-id.apps.googleusercontent.com")
    client = app.test_client()
    paths = (
        "/shop/collections",
        "/shop/shipping",
        "/shop/checkout",
        "/shop/our-story",
        "/shop/shipping-returns",
        "/shop/terms",
        "/shop/privacy-policy",
        "/shop/orders",
    )

    for path in paths:
        response = client.get(path)

        assert response.status_code == 200, path
        assert (
            'data-client_id="custom-client-id.apps.googleusercontent.com"'
            in response.get_data(as_text=True)
        ), path
