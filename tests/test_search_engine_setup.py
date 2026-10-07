import json
import re
from pathlib import Path

from app import app


def test_google_verification_file_is_public_and_unchanged():
    response = app.test_client().get("/googled9f82b121fbf0657.html")
    original = Path(app.static_folder) / "search-verification" / "googled9f82b121fbf0657.html"
    assert response.status_code == 200
    assert response.data == original.read_bytes()
    assert response.mimetype == "text/html"
    assert b"google-site-verification: googled9f82b121fbf0657.html" in response.data


def test_bing_verification_file_is_public_and_unchanged():
    response = app.test_client().get("/BingSiteAuth.xml")
    original = Path(app.static_folder) / "search-verification" / "BingSiteAuth.xml"
    assert response.status_code == 200
    assert response.data == original.read_bytes()
    assert response.mimetype == "application/xml"


def test_homepage_identifies_the_site_name():
    for path in ("/", "/shop/"):
        page = app.test_client().get(path).get_data(as_text=True)
        data = [json.loads(value) for value in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', page
        )]
        website = next(item for item in data if item.get("@type") == "WebSite")
        assert website["url"] == "https://thugilethreads.store/"
        assert website["name"] == "Thugile & Threads"


def test_search_verification_tokens_are_in_the_head_and_escaped(monkeypatch):
    monkeypatch.setenv("GOOGLE_SITE_VERIFICATION", 'google-token"<test>')
    monkeypatch.setenv("BING_SITE_VERIFICATION", "bing-token")
    page = app.test_client().get("/").get_data(as_text=True)
    head = page.split("</head>", 1)[0]
    assert '<meta name="google-site-verification" content="google-token&quot;&lt;test&gt;">' in head
    assert '<meta name="msvalidate.01" content="bing-token">' in head


def test_empty_verification_settings_do_not_publish_placeholder_tags(monkeypatch):
    monkeypatch.delenv("GOOGLE_SITE_VERIFICATION", raising=False)
    monkeypatch.delenv("BING_SITE_VERIFICATION", raising=False)
    page = app.test_client().get("/").get_data(as_text=True)
    assert 'name="google-site-verification"' not in page
    assert 'name="msvalidate.01"' not in page
