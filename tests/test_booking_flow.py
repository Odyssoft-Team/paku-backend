from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_hold_returns_201_and_status_held():
    email = "test_booking_flow_hold_" + __import__("uuid").uuid4().hex + "@example.com"
    password = "123456"

    client.post("/auth/register", json={
        "email": email,
        "password": password,
        "phone": "+51999999999",
        "first_name": "Test",
        "last_name": "User",
        "sex": "male",
        "birth_date": "1990-01-01",
    })
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]

    pet_resp = client.post(
        "/pets",
        json={"name": "Firulais", "species": "dog"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pet_resp.status_code == 201
    pet_id = pet_resp.json()["id"]

    service_id = "11111111-1111-1111-1111-111111111111"
    hold_resp = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": service_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert hold_resp.status_code == 201
    data = hold_resp.json()
    assert data.get("status") == "held"
    assert "expires_at" in data


def test_confirm_hold_changes_status():
    email = "test_booking_flow_confirm_" + __import__("uuid").uuid4().hex + "@example.com"
    password = "123456"

    client.post("/auth/register", json={
        "email": email,
        "password": password,
        "phone": "+51999999999",
        "first_name": "Test",
        "last_name": "User",
        "sex": "male",
        "birth_date": "1990-01-01",
    })
    login = client.post("/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]

    pet_resp = client.post(
        "/pets",
        json={"name": "Michi", "species": "cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pet_id = pet_resp.json()["id"]
    service_id = "33333333-3333-3333-3333-333333333333"

    hold_resp = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": service_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    hold_id = hold_resp.json()["id"]

    confirm_resp = client.post(f"/holds/{hold_id}/confirm")
    assert confirm_resp.status_code == 200
    assert confirm_resp.json().get("status") == "confirmed"


def test_cancel_hold_is_idempotent():
    email = "test_booking_flow_cancel_" + __import__("uuid").uuid4().hex + "@example.com"
    password = "123456"

    client.post("/auth/register", json={
        "email": email,
        "password": password,
        "phone": "+51999999999",
        "first_name": "Test",
        "last_name": "User",
        "sex": "male",
        "birth_date": "1990-01-01",
    })
    login = client.post("/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]

    pet_resp = client.post(
        "/pets",
        json={"name": "Rex", "species": "dog"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pet_id = pet_resp.json()["id"]
    service_id = "11111111-1111-1111-1111-111111111111"

    hold_resp = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": service_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    hold_id = hold_resp.json()["id"]

    cancel1 = client.post(f"/holds/{hold_id}/cancel")
    assert cancel1.status_code == 200
    assert cancel1.json().get("status") == "cancelled"

    cancel2 = client.post(f"/holds/{hold_id}/cancel")
    assert cancel2.status_code == 200
    assert cancel2.json().get("status") == "cancelled"


def test_confirm_nonexistent_hold_returns_404():
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"/holds/{fake_id}/confirm")
    assert r.status_code == 404
