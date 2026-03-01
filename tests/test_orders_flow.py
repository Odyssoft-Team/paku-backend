from fastapi.testclient import TestClient
from app.main import app


def _auth_headers(client: TestClient, *, email: str, password: str) -> dict:
    register_payload = {
        "email": email,
        "password": password,
        "phone": "999999999",
        "first_name": "Test",
        "last_name": "User",
        "sex": "male",
        "birth_date": "1990-01-01",
        "role": "user",
        "dni": None,
        "address": None,
        "profile_photo_url": None,
    }
    client.post("/auth/register", json=register_payload)

    login_payload = {"email": email, "password": password}
    r = client.post("/auth/login", json=login_payload)
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_order_from_checked_out_cart_creates_notification():
    client = TestClient(app)
    headers = _auth_headers(client, email="orders_user_" + __import__("uuid").uuid4().hex + "@example.com", password="pass1234")

    r = client.post("/cart", headers=headers)
    assert r.status_code in (200, 201)
    cart_id = r.json()["id"]

    payload = {"kind": "product", "ref_id": "p1", "qty": 1}
    r = client.post(f"/cart/{cart_id}/items", json=payload, headers=headers)
    assert r.status_code in (200, 201)

    r = client.post(f"/cart/{cart_id}/checkout", headers=headers)
    assert r.status_code == 200

    r = client.post("/orders", json={"cart_id": cart_id}, headers=headers)
    assert r.status_code in (200, 201)
    order = r.json()
    assert order["status"] == "created"

    r = client.get("/notifications", headers=headers)
    assert r.status_code == 200
    notifs = r.json()
    order_status_notifs = [n for n in notifs if n.get("type") == "order_status"]
    assert len(order_status_notifs) >= 1


def test_list_orders_returns_created_order():
    client = TestClient(app)
    headers = _auth_headers(client, email="orders_list_" + __import__("uuid").uuid4().hex + "@example.com", password="pass1234")

    r = client.post("/cart", headers=headers)
    assert r.status_code in (200, 201)
    cart_id = r.json()["id"]

    payload = {"kind": "product", "ref_id": "p1", "qty": 1}
    r = client.post(f"/cart/{cart_id}/items", json=payload, headers=headers)
    assert r.status_code in (200, 201)

    r = client.post(f"/cart/{cart_id}/checkout", headers=headers)
    assert r.status_code == 200

    r = client.post("/orders", json={"cart_id": cart_id}, headers=headers)
    assert r.status_code in (200, 201)

    r = client.get("/orders", headers=headers)
    assert r.status_code == 200
    orders = r.json()
    assert isinstance(orders, list)
    assert len(orders) >= 1
    assert "id" in orders[0]


def test_get_order_by_id_for_owner_ok():
    client = TestClient(app)
    headers = _auth_headers(client, email="orders_get_" + __import__("uuid").uuid4().hex + "@example.com", password="pass1234")

    r = client.post("/cart", headers=headers)
    assert r.status_code in (200, 201)
    cart_id = r.json()["id"]

    payload = {"kind": "product", "ref_id": "p1", "qty": 1}
    r = client.post(f"/cart/{cart_id}/items", json=payload, headers=headers)
    assert r.status_code in (200, 201)

    r = client.post(f"/cart/{cart_id}/checkout", headers=headers)
    assert r.status_code == 200

    r = client.post("/orders", json={"cart_id": cart_id}, headers=headers)
    assert r.status_code in (200, 201)
    order_id = r.json()["id"]

    r = client.get(f"/orders/{order_id}", headers=headers)
    assert r.status_code == 200
    order = r.json()
    assert order["id"] == order_id


def test_update_status_requires_admin_or_ally():
    client = TestClient(app)
    headers = _auth_headers(client, email="orders_status_" + __import__("uuid").uuid4().hex + "@example.com", password="pass1234")

    r = client.post("/cart", headers=headers)
    assert r.status_code in (200, 201)
    cart_id = r.json()["id"]

    payload = {"kind": "product", "ref_id": "p1", "qty": 1}
    r = client.post(f"/cart/{cart_id}/items", json=payload, headers=headers)
    assert r.status_code in (200, 201)

    r = client.post(f"/cart/{cart_id}/checkout", headers=headers)
    assert r.status_code == 200

    r = client.post("/orders", json={"cart_id": cart_id}, headers=headers)
    assert r.status_code in (200, 201)
    order_id = r.json()["id"]

    r = client.post(f"/orders/{order_id}/status", json={"status": "on_the_way"}, headers=headers)
    assert r.status_code == 403
