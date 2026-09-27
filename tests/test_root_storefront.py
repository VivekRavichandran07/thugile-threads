from app import app


def test_root_serves_the_storefront_without_shop_path():
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "<title>Thugile & Threads | Chudidar Edit</title>" in response.get_data(as_text=True)
