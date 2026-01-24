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


def test_register_and_list_devices():
    client = TestClient(app)
    headers = _auth_headers(client, email="push_user_" + __import__("uuid").uuid4().hex + "@example.com", password="pass1234")

    payload = {"platform": "android", "token": "token123"}
    r = client.post("/push/devices", json=payload, headers=headers)
    assert r.status_code == 201
    device = r.json()
    assert device["platform"] == "android"
    assert device["token"] == "token123"
    assert device["is_active"] is True
    device_id = device["id"]

    r = client.get("/push/devices", headers=headers)
    assert r.status_code == 200
    devices = r.json()
    assert isinstance(devices, list)
    assert len(devices) >= 1
    assert any(d["id"] == device_id for d in devices)


def test_register_same_platform_updates_token():
    client = TestClient(app)
    headers = _auth_headers(client, email="push_update_" + __import__("uuid").uuid4().hex + "@example.com", password="pass1234")

    payload = {"platform": "ios", "token": "old-token"}
    r = client.post("/push/devices", json=payload, headers=headers)
    assert r.status_code == 201
    device_id = r.json()["id"]

    payload = {"platform": "ios", "token": "new-token"}
    r = client.post("/push/devices", json=payload, headers=headers)
    assert r.status_code == 201
    updated = r.json()
    assert updated["id"] == device_id
    assert updated["token"] == "new-token"
    assert updated["is_active"] is True

    r = client.get("/push/devices", headers=headers)
    devices = r.json()
    ios_devices = [d for d in devices if d["platform"] == "ios"]
    assert len(ios_devices) == 1
    assert ios_devices[0]["token"] == "new-token"


def test_deactivate_device():
    client = TestClient(app)
    headers = _auth_headers(client, email="push_deactivate_" + __import__("uuid").uuid4().hex + "@example.com", password="pass1234")

    payload = {"platform": "web", "token": "web-token"}
    r = client.post("/push/devices", json=payload, headers=headers)
    assert r.status_code == 201
    device_id = r.json()["id"]

    r = client.delete(f"/push/devices/{device_id}", headers=headers)
    assert r.status_code == 204

    r = client.get("/push/devices", headers=headers)
    devices = r.json()
    deactivated = next(d for d in devices if d["id"] == device_id)
    assert deactivated["is_active"] is False


def test_deactivate_nonexistent_returns_404():
    client = TestClient(app)
    headers = _auth_headers(client, email="push_404_" + __import__("uuid").uuid4().hex + "@example.com", password="pass1234")
    fake_id = __import__("uuid").uuid4()
    r = client.delete(f"/push/devices/{fake_id}", headers=headers)
    assert r.status_code == 404
