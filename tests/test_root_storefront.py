from app import app


def test_root_serves_the_storefront_without_shop_path():
    response = app.test_client().get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "<title>Thugile &amp; Threads | Chudidar &amp; Indian Occasionwear</title>" in page
    assert '<link rel="canonical" href="https://thugilethreads.store/">' in page
    assert 'property="og:title"' in page
    assert 'type="application/ld+json"' in page


def test_robots_and_sitemap_only_publish_public_store_pages():
    client = app.test_client()

    robots = client.get("/robots.txt").get_data(as_text=True)
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)

    assert "Disallow: /admin/" in robots
    assert "Disallow: /api/" in robots
    assert "Disallow: /shop/reset-password" in robots
    assert "Sitemap: https://thugilethreads.store/sitemap.xml" in robots
    assert "https://thugilethreads.store/shop/collections" in sitemap
    assert "/api/" not in sitemap
    assert "/admin/" not in sitemap


def test_store_pages_have_distinct_metadata_and_product_schema():
    client = app.test_client()
    home = client.get("/").get_data(as_text=True)
    collections = client.get("/shop/collections").get_data(as_text=True)
    contact = client.get("/shop/contact/").get_data(as_text=True)
    checkout = client.get("/shop/checkout").get_data(as_text=True)

    assert "Discover thoughtfully made chudidars" in home
    assert "Explore handcrafted chudidar sets" in collections
    assert "Contact Thugile &amp; Threads about orders" in contact
    assert '<link rel="canonical" href="https://thugilethreads.store/shop/contact">' in contact
    assert '"@type":"Product"' in collections
    assert '<meta name="robots" content="noindex, nofollow">' in checkout


def test_orders_redirects_to_the_combined_account_page():
    client = app.test_client()
    response = client.get("/shop/orders")
    assert response.status_code == 302
    assert response.headers["Location"] == "/shop/shipping"
    assert client.get("/shop/orders", follow_redirects=True).data == client.get("/shop/shipping").data


def test_account_page_contains_addresses_and_order_history():
    response = app.test_client().get("/shop/shipping")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for element_id in ("addresses-list", "shipping-form", "orders-list", "address-selection-error"):
        assert html.count(f'id="{element_id}"') == 1
    assert html.index('id="addresses-list"') < html.index('id="orders-list"')
