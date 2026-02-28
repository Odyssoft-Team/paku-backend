"""Integration tests: Order creation and status update trigger push notifications."""
import uuid

from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(client: TestClient, *, email: str, password: str, role: str = "user") -> dict:
    register_payload = {
        "email": email,
        "password": password,
        "phone": "999999999",
        "first_name": "Test",
        "last_name": "User",
        "sex": "male",
        "birth_date": "1990-01-01",
        "role": role,
        "dni": None,
        "address": None,
        "profile_photo_url": None,
    }
    client.post("/auth/register", json=register_payload)
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_checked_out_cart(client: TestClient, headers: dict) -> str:
    r = client.post("/cart", headers=headers)
    assert r.status_code in (200, 201)
    cart_id = r.json()["id"]

    r = client.post(
        f"/cart/{cart_id}/items",
        json={"kind": "product", "ref_id": "p1", "qty": 1},
        headers=headers,
    )
    assert r.status_code in (200, 201)

    r = client.post(f"/cart/{cart_id}/checkout", headers=headers)
    assert r.status_code == 200

    return cart_id


def test_create_order_sends_push_to_registered_device(monkeypatch):
    captured = []

    def fake_send(self, tokens, message):
        captured.append({"tokens": tokens, "title": message.title, "body": message.body})

    monkeypatch.setattr("app.modules.push.infra.provider.MockPushProvider.send", fake_send)

    client = TestClient(app)
    email = f"push_order_{uuid.uuid4().hex}@example.com"
    headers = _auth_headers(client, email=email, password="pass1234")

    r = client.post(
        "/push/devices",
        json={"platform": "android", "token": "ExponentPushToken[test-order-001]"},
        headers=headers,
    )
    assert r.status_code == 201

    cart_id = _create_checked_out_cart(client, headers)

    r = client.post("/orders", json={"cart_id": cart_id}, headers=headers)
    assert r.status_code in (200, 201)

    assert len(captured) >= 1, "MockPushProvider.send no fue invocado al crear el order"
    tokens_sent = captured[0]["tokens"]
    assert "ExponentPushToken[test-order-001]" in tokens_sent


def test_create_order_no_push_when_no_device_registered(monkeypatch):
    captured = []

    def fake_send(self, tokens, message):
        captured.append({"tokens": tokens})

    monkeypatch.setattr("app.modules.push.infra.provider.MockPushProvider.send", fake_send)

    client = TestClient(app)
    email = f"push_nodevice_{uuid.uuid4().hex}@example.com"
    headers = _auth_headers(client, email=email, password="pass1234")

    cart_id = _create_checked_out_cart(client, headers)
    r = client.post("/orders", json={"cart_id": cart_id}, headers=headers)
    assert r.status_code in (200, 201)

    assert len(captured) == 0, "No debería enviar push si no hay device tokens registrados"


def test_update_order_status_sends_push(monkeypatch):
    captured = []

    def fake_send(self, tokens, message):
        captured.append({"tokens": tokens, "title": message.title})

    monkeypatch.setattr("app.modules.push.infra.provider.MockPushProvider.send", fake_send)

    client = TestClient(app)
    user_email = f"push_status_user_{uuid.uuid4().hex}@example.com"
    admin_email = f"push_status_admin_{uuid.uuid4().hex}@example.com"

    user_headers = _auth_headers(client, email=user_email, password="pass1234", role="user")
    admin_headers = _auth_headers(client, email=admin_email, password="pass1234", role="admin")

    r = client.post(
        "/push/devices",
        json={"platform": "ios", "token": "ExponentPushToken[test-status-001]"},
        headers=user_headers,
    )
    assert r.status_code == 201

    cart_id = _create_checked_out_cart(client, user_headers)
    r = client.post("/orders", json={"cart_id": cart_id}, headers=user_headers)
    assert r.status_code in (200, 201)
    order_id = r.json()["id"]

    # Reset captured after order creation push
    captured.clear()

    r = client.post(
        f"/orders/{order_id}/status",
        json={"status": "in_process"},
        headers=admin_headers,
    )
    assert r.status_code == 200

    assert len(captured) >= 1, "MockPushProvider.send no fue invocado al actualizar status"
    tokens_sent = captured[0]["tokens"]
    assert "ExponentPushToken[test-status-001]" in tokens_sent


def test_deactivated_device_does_not_receive_push(monkeypatch):
    captured = []

    def fake_send(self, tokens, message):
        captured.append({"tokens": tokens})

    monkeypatch.setattr("app.modules.push.infra.provider.MockPushProvider.send", fake_send)

    client = TestClient(app)
    email = f"push_deact_{uuid.uuid4().hex}@example.com"
    headers = _auth_headers(client, email=email, password="pass1234")

    r = client.post(
        "/push/devices",
        json={"platform": "android", "token": "ExponentPushToken[deact-token]"},
        headers=headers,
    )
    assert r.status_code == 201
    device_id = r.json()["id"]

    r = client.delete(f"/push/devices/{device_id}", headers=headers)
    assert r.status_code == 204

    cart_id = _create_checked_out_cart(client, headers)
    r = client.post("/orders", json={"cart_id": cart_id}, headers=headers)
    assert r.status_code in (200, 201)

    assert len(captured) == 0, "No debería enviar push a device desactivado"
