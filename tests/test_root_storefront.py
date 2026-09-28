from app import app


def test_root_serves_the_storefront_without_shop_path():
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "<title>Thugile & Threads | Chudidar Edit</title>" in response.get_data(as_text=True)


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
