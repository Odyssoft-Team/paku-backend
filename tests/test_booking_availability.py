from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_availability_requires_auth():
    r = client.get("/availability?service_id=11111111-1111-1111-1111-111111111111")
    # FastAPI con HTTPBearer devuelve 403 si falta Authorization
    assert r.status_code in (401, 403)


def test_availability_returns_7_days_by_default():
    email = "test_booking_availability@example.com"
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

    r = client.get(
        "/availability?service_id=11111111-1111-1111-1111-111111111111",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 7
    for item in data:
        assert "date" in item
        assert "capacity" in item
        assert "available" in item
