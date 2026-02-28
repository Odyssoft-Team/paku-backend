"""Booking flow tests — holds con validación real de availability slots."""
import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.main import app

SERVICE_DOG = "11111111-1111-1111-1111-111111111111"
SERVICE_CAT = "33333333-3333-3333-3333-333333333333"


def _register_and_login(client: TestClient, *, role: str = "user") -> str:
    email = f"booking_{uuid.uuid4().hex}@example.com"
    client.post("/auth/register", json={
        "email": email,
        "password": "pass1234",
        "phone": "+51999999999",
        "first_name": "Test",
        "last_name": "User",
        "sex": "male",
        "birth_date": "1990-01-01",
        "role": role,
    })
    r = client.post("/auth/login", json={"email": email, "password": "pass1234"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_slot(client: TestClient, admin_token: str, *, service_id: str, slot_date: date, capacity: int = 10) -> dict:
    r = client.post(
        "/admin/availability",
        json={"service_id": service_id, "date": str(slot_date), "capacity": capacity, "is_active": True},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _create_pet(client: TestClient, token: str, *, species: str = "dog") -> str:
    r = client.post(
        "/pets",
        json={"name": "Firulais", "species": species},
        headers=_auth(token),
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_create_hold_returns_201_and_status_held():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")
    user_token = _register_and_login(client)

    slot_date = date(2030, 3, 1)
    _create_slot(client, admin_token, service_id=SERVICE_DOG, slot_date=slot_date)

    pet_id = _create_pet(client, user_token, species="dog")

    r = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": SERVICE_DOG, "date": str(slot_date)},
        headers=_auth(user_token),
    )
    assert r.status_code == 201, r.json()
    data = r.json()
    assert data["status"] == "held"
    assert data["date"] == str(slot_date)
    assert "expires_at" in data


def test_confirm_hold_changes_status():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")
    user_token = _register_and_login(client)

    slot_date = date(2030, 3, 2)
    _create_slot(client, admin_token, service_id=SERVICE_CAT, slot_date=slot_date)

    pet_id = _create_pet(client, user_token, species="cat")

    r = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": SERVICE_CAT, "date": str(slot_date)},
        headers=_auth(user_token),
    )
    assert r.status_code == 201, r.json()
    hold_id = r.json()["id"]

    r = client.post(f"/holds/{hold_id}/confirm", headers=_auth(user_token))
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"


def test_cancel_hold_is_idempotent():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")
    user_token = _register_and_login(client)

    slot_date = date(2030, 3, 3)
    _create_slot(client, admin_token, service_id=SERVICE_DOG, slot_date=slot_date)

    pet_id = _create_pet(client, user_token, species="dog")

    r = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": SERVICE_DOG, "date": str(slot_date)},
        headers=_auth(user_token),
    )
    assert r.status_code == 201, r.json()
    hold_id = r.json()["id"]

    r = client.post(f"/holds/{hold_id}/cancel", headers=_auth(user_token))
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    r = client.post(f"/holds/{hold_id}/cancel", headers=_auth(user_token))
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_cancel_hold_decrements_booked():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")
    user_token = _register_and_login(client)

    slot_date = date(2030, 3, 4)
    slot = _create_slot(client, admin_token, service_id=SERVICE_DOG, slot_date=slot_date, capacity=5)
    slot_id = slot["id"]

    pet_id = _create_pet(client, user_token, species="dog")

    r = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": SERVICE_DOG, "date": str(slot_date)},
        headers=_auth(user_token),
    )
    assert r.status_code == 201
    hold_id = r.json()["id"]

    r = client.get("/admin/availability", params={"service_id": SERVICE_DOG}, headers=_auth(admin_token))
    slot_after_hold = next(s for s in r.json() if s["id"] == slot_id)
    assert slot_after_hold["booked"] == 1

    client.post(f"/holds/{hold_id}/cancel", headers=_auth(user_token))

    r = client.get("/admin/availability", params={"service_id": SERVICE_DOG}, headers=_auth(admin_token))
    slot_after_cancel = next(s for s in r.json() if s["id"] == slot_id)
    assert slot_after_cancel["booked"] == 0


def test_hold_fails_when_no_slot_exists():
    client = TestClient(app)
    user_token = _register_and_login(client)
    pet_id = _create_pet(client, user_token, species="dog")

    r = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": SERVICE_DOG, "date": "2099-12-31"},
        headers=_auth(user_token),
    )
    assert r.status_code == 409
    assert "no_availability" in r.json()["detail"]


def test_hold_fails_when_slot_at_capacity():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")
    user_token = _register_and_login(client)

    slot_date = date(2030, 3, 5)
    _create_slot(client, admin_token, service_id=SERVICE_DOG, slot_date=slot_date, capacity=1)

    pet_id = _create_pet(client, user_token, species="dog")

    r = client.post(
        "/holds",
        json={"pet_id": pet_id, "service_id": SERVICE_DOG, "date": str(slot_date)},
        headers=_auth(user_token),
    )
    assert r.status_code == 201

    # Second hold should fail — capacity=1 is full
    user2_token = _register_and_login(client)
    pet2_id = _create_pet(client, user2_token, species="dog")

    r = client.post(
        "/holds",
        json={"pet_id": pet2_id, "service_id": SERVICE_DOG, "date": str(slot_date)},
        headers=_auth(user2_token),
    )
    assert r.status_code == 409
    assert "no_capacity" in r.json()["detail"]


def test_confirm_nonexistent_hold_returns_404():
    client = TestClient(app)
    user_token = _register_and_login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"/holds/{fake_id}/confirm", headers=_auth(user_token))
    assert r.status_code == 404
