import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _register_and_login() -> str:
    email = "test_pets_flow_" + uuid.uuid4().hex + "@example.com"
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
    return login.json()["access_token"]


def _create_pet(token: str, name: str = "Firulais") -> str:
    r = client.post(
        "/pets",
        json={"name": name, "species": "dog"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_create_pet_ok():
    email = "test_pets_flow_ok_" + __import__("uuid").uuid4().hex + "@example.com"
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

    r = client.post(
        "/pets",
        json={"name": "Firulais", "species": "dog"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert "owner_id" in data
    assert data.get("species") == "dog"


def test_create_pet_invalid_species():
    email = "test_pets_flow_invalid_species_" + __import__("uuid").uuid4().hex + "@example.com"
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

    r = client.post(
        "/pets",
        json={"name": "Birdy", "species": "bird"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_get_pet_by_id():
    email = "test_pets_flow_get_by_id_" + __import__("uuid").uuid4().hex + "@example.com"
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

    created = client.post(
        "/pets",
        json={"name": "Michi", "species": "cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    pet_id = created.json()["id"]

    r = client.get(f"/pets/{pet_id}")
    assert r.status_code == 200
    data = r.json()
    assert data.get("name") == "Michi"
    assert data.get("species") == "cat"


def test_delete_own_pet_ok():
    token = _register_and_login()
    pet_id = _create_pet(token)
    auth = {"Authorization": f"Bearer {token}"}

    r = client.delete(f"/pets/{pet_id}", headers=auth)
    assert r.status_code == 204

    assert client.get(f"/pets/{pet_id}").status_code == 404

    listed = client.get("/pets", headers=auth)
    assert listed.status_code == 200
    assert all(p["id"] != pet_id for p in listed.json())


def test_delete_pet_twice_returns_404():
    token = _register_and_login()
    pet_id = _create_pet(token)
    auth = {"Authorization": f"Bearer {token}"}

    assert client.delete(f"/pets/{pet_id}", headers=auth).status_code == 204
    assert client.delete(f"/pets/{pet_id}", headers=auth).status_code == 404


def test_delete_missing_pet_404():
    token = _register_and_login()
    r = client.delete(f"/pets/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_delete_other_users_pet_forbidden():
    owner_token = _register_and_login()
    pet_id = _create_pet(owner_token)

    other_token = _register_and_login()
    r = client.delete(f"/pets/{pet_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert r.status_code == 403

    still_there = client.get(f"/pets/{pet_id}")
    assert still_there.status_code == 200
