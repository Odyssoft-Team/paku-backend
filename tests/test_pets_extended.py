from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _register_and_login(email: str) -> str:
    password = "123456"
    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "phone": "+51999999999",
            "first_name": "Test",
            "last_name": "User",
            "sex": "male",
            "birth_date": "1990-01-01",
        },
    )
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_pet(*, token: str, name: str = "Firulais", species: str = "dog") -> dict:
    r = client.post("/pets", json={"name": name, "species": species}, headers=_auth_headers(token))
    assert r.status_code == 201
    return r.json()


def _parse_dt(value: str) -> datetime:
    # Manejo básico de ISO con o sin 'Z'
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def test_update_pet_editable_fields_ok():
    token = _register_and_login("test_pets_extended_update_ok@example.com")
    pet = _create_pet(token=token, name="Firulais", species="dog")

    payload = {"name": "Firulais 2", "photo_url": "https://example.com/pets/1.jpg"}
    r = client.put(f"/pets/{pet['id']}", json=payload, headers=_auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data.get("name") == payload["name"]
    assert data.get("photo_url") == payload["photo_url"]


def test_update_pet_cannot_change_species():
    token = _register_and_login("test_pets_extended_update_species@example.com")
    pet = _create_pet(token=token, name="Firulais", species="dog")

    r = client.put(
        f"/pets/{pet['id']}",
        json={"species": "cat"},
        headers=_auth_headers(token),
    )

    # En este proyecto, el schema de update puede ignorar campos extra (200)
    # o rechazar (400/422). Aceptamos el comportamiento real.
    if r.status_code == 200:
        reread = client.get(f"/pets/{pet['id']}")
        assert reread.status_code == 200
        assert reread.json().get("species") == "dog"
    else:
        assert r.status_code in (400, 422)


def test_update_pet_forbidden_if_not_owner():
    token_a = _register_and_login("test_pets_extended_owner_a@example.com")
    token_b = _register_and_login("test_pets_extended_owner_b@example.com")
    pet = _create_pet(token=token_a, name="Firulais", species="dog")

    r = client.put(
        f"/pets/{pet['id']}",
        json={"name": "Hacked"},
        headers=_auth_headers(token_b),
    )
    assert r.status_code == 403


def test_add_weight_updates_current_weight_and_creates_history_entry():
    token = _register_and_login("test_pets_extended_weight_add@example.com")
    pet = _create_pet(token=token, name="Firulais", species="dog")

    r = client.post(
        f"/pets/{pet['id']}/weight",
        json={"weight_kg": 12.5},
        headers=_auth_headers(token),
    )
    assert r.status_code in (200, 201)
    entry = r.json()
    assert entry.get("pet_id") == pet["id"]
    assert entry.get("weight_kg") == 12.5

    reread = client.get(f"/pets/{pet['id']}")
    assert reread.status_code == 200
    assert reread.json().get("weight_kg") == 12.5


def test_weight_history_returns_entries_desc():
    token = _register_and_login("test_pets_extended_weight_history@example.com")
    pet = _create_pet(token=token, name="Firulais", species="dog")

    r1 = client.post(
        f"/pets/{pet['id']}/weight",
        json={"weight_kg": 10.0},
        headers=_auth_headers(token),
    )
    assert r1.status_code in (200, 201)

    r2 = client.post(
        f"/pets/{pet['id']}/weight",
        json={"weight_kg": 11.0},
        headers=_auth_headers(token),
    )
    assert r2.status_code in (200, 201)

    r = client.get(f"/pets/{pet['id']}/weight-history")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 2

    t0 = _parse_dt(data[0]["recorded_at"])
    t1 = _parse_dt(data[1]["recorded_at"])
    assert t0 >= t1
