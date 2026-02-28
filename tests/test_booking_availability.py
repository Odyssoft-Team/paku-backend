"""Availability endpoint tests — slots reales desde DB."""
import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

SERVICE_DOG = "11111111-1111-1111-1111-111111111111"


def _register_and_login(client: TestClient, *, role: str = "user") -> str:
    email = f"avail_{uuid.uuid4().hex}@example.com"
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


def test_availability_requires_auth():
    client = TestClient(app)
    r = client.get(f"/availability?service_id={SERVICE_DOG}")
    assert r.status_code in (401, 403)


def test_availability_returns_only_active_slots():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")
    user_token = _register_and_login(client)

    base_date = date(2030, 4, 1)

    # Crear 3 slots activos y 1 inactivo
    active_slot_ids = []
    for i in range(3):
        r = client.post(
            "/admin/availability",
            json={"service_id": SERVICE_DOG, "date": str(base_date + timedelta(days=i)), "capacity": 10},
            headers=_auth(admin_token),
        )
        assert r.status_code == 201
        active_slot_ids.append(r.json()["id"])

    r = client.post(
        "/admin/availability",
        json={"service_id": SERVICE_DOG, "date": str(base_date + timedelta(days=10)), "capacity": 5},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201
    inactive_slot_id = r.json()["id"]

    client.post(
        f"/admin/availability/{inactive_slot_id}/toggle",
        json={"is_active": False},
        headers=_auth(admin_token),
    )

    r = client.get(
        "/availability",
        params={"service_id": SERVICE_DOG, "date_from": str(base_date), "days": 30},
        headers=_auth(user_token),
    )
    assert r.status_code == 200
    data = r.json()

    returned_ids = {s["id"] for s in data}
    for slot_id in active_slot_ids:
        assert slot_id in returned_ids
    assert inactive_slot_id not in returned_ids


def test_availability_shape():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")
    user_token = _register_and_login(client)

    slot_date = date(2030, 5, 1)
    client.post(
        "/admin/availability",
        json={"service_id": SERVICE_DOG, "date": str(slot_date), "capacity": 8},
        headers=_auth(admin_token),
    )

    r = client.get(
        "/availability",
        params={"service_id": SERVICE_DOG, "date_from": str(slot_date), "days": 1},
        headers=_auth(user_token),
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1

    item = next(s for s in data if s["date"] == str(slot_date))
    assert item["capacity"] == 8
    assert item["booked"] == 0
    assert item["available"] == 8
    assert item["is_active"] is True
    assert "id" in item
    assert "service_id" in item


def test_admin_list_includes_inactive_slots():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    slot_date = date(2030, 6, 1)
    r = client.post(
        "/admin/availability",
        json={"service_id": SERVICE_DOG, "date": str(slot_date), "capacity": 3, "is_active": False},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201
    slot_id = r.json()["id"]

    r = client.get(
        "/admin/availability",
        params={"service_id": SERVICE_DOG, "date_from": str(slot_date), "days": 1},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    returned_ids = {s["id"] for s in r.json()}
    assert slot_id in returned_ids


def test_admin_update_slot_capacity():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    slot_date = date(2030, 7, 1)
    r = client.post(
        "/admin/availability",
        json={"service_id": SERVICE_DOG, "date": str(slot_date), "capacity": 5},
        headers=_auth(admin_token),
    )
    assert r.status_code == 201
    slot_id = r.json()["id"]

    r = client.patch(
        f"/admin/availability/{slot_id}",
        json={"capacity": 20},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["capacity"] == 20


def test_availability_admin_requires_admin_role():
    client = TestClient(app)
    user_token = _register_and_login(client, role="user")

    r = client.post(
        "/admin/availability",
        json={"service_id": SERVICE_DOG, "date": "2030-08-01", "capacity": 5},
        headers=_auth(user_token),
    )
    assert r.status_code == 403
