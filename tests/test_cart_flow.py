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


def test_create_cart_returns_active_and_expires_at():
    client = TestClient(app)
    headers = _auth_headers(client, email="cart_a@example.com", password="pass1234")

    r = client.post("/cart", headers=headers)
    assert r.status_code in (200, 201)
    data = r.json()
    assert data["status"] == "active"
    assert "expires_at" in data


def test_add_item_and_get_cart_returns_items():
    client = TestClient(app)
    headers = _auth_headers(client, email="cart_b@example.com", password="pass1234")

    r = client.post("/cart", headers=headers)
    assert r.status_code in (200, 201)
    cart_id = r.json()["id"]

    payload = {
        "kind": "product",
        "ref_id": "p1",
        "qty": 1,
    }
    r = client.post(f"/cart/{cart_id}/items", json=payload, headers=headers)
    assert r.status_code in (200, 201)

    r = client.get(f"/cart/{cart_id}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) >= 1


def test_checkout_marks_checked_out():
    client = TestClient(app)
    headers = _auth_headers(client, email="cart_c@example.com", password="pass1234")

    r = client.post("/cart", headers=headers)
    assert r.status_code in (200, 201)
    cart_id = r.json()["id"]

    payload = {
        "kind": "product",
        "ref_id": "p1",
        "qty": 1,
    }
    r = client.post(f"/cart/{cart_id}/items", json=payload, headers=headers)
    assert r.status_code in (200, 201)

    r = client.post(f"/cart/{cart_id}/checkout", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "checked_out"


def test_cart_forbidden_if_not_owner():
    client = TestClient(app)

    headers_a = _auth_headers(client, email="cart_owner_a@example.com", password="pass1234")
    headers_b = _auth_headers(client, email="cart_owner_b@example.com", password="pass1234")

    r = client.post("/cart", headers=headers_a)
    assert r.status_code in (200, 201)
    cart_id = r.json()["id"]

    r = client.get(f"/cart/{cart_id}", headers=headers_b)
    assert r.status_code in (403, 404)
