from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_register_returns_201():
    payload = {"email": "test_iam_flow_user@example.com", "password": "123456"}
    r = client.post("/auth/register", json=payload)
    # Este proyecto retorna 201 en register
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data.get("email") == payload["email"]


def test_login_returns_tokens():
    payload = {"email": "test_iam_flow_user@example.com", "password": "123456"}
    r = client.post("/auth/login", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    if "refresh_token" in data:
        assert data["refresh_token"]


def test_me_requires_auth():
    r = client.get("/users/me")
    # El proyecto responde 403 si falta Authorization (HTTPBearer)
    assert r.status_code in (401, 403)


def test_me_with_token_returns_user():
    login_payload = {"email": "test_iam_flow_user@example.com", "password": "123456"}
    login = client.post("/auth/login", json=login_payload)
    assert login.status_code == 200
    access_token = login.json()["access_token"]

    r = client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("email") == login_payload["email"]
    assert "role" in data
