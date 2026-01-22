from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_pet_ok():
    email = "test_pets_flow_ok@example.com"
    password = "123456"

    client.post("/auth/register", json={"email": email, "password": password})
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
    email = "test_pets_flow_invalid_species@example.com"
    password = "123456"

    client.post("/auth/register", json={"email": email, "password": password})
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
    email = "test_pets_flow_get_by_id@example.com"
    password = "123456"

    client.post("/auth/register", json={"email": email, "password": password})
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
