"""Tests for commerce admin endpoints.

Covers:
  GET    /admin/services
  POST   /admin/services
  PATCH  /admin/services/{id}
  POST   /admin/services/{id}/toggle
  GET    /admin/services/{id}/price-rules
  POST   /admin/price-rules
  PATCH  /admin/price-rules/{id}
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app


def _register_and_login(client: TestClient, *, role: str = "user") -> str:
    email = f"commerce_admin_{uuid.uuid4().hex}@example.com"
    client.post("/auth/register", json={
        "email": email,
        "password": "pass1234",
        "phone": "999999999",
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


# ------------------------------------------------------------------
# Access control
# ------------------------------------------------------------------

def test_admin_services_requires_admin_role():
    client = TestClient(app)
    user_token = _register_and_login(client, role="user")
    assert client.get("/admin/services", headers=_auth(user_token)).status_code == 403
    assert client.post("/admin/services", json={}, headers=_auth(user_token)).status_code == 403


def test_admin_services_requires_auth():
    client = TestClient(app)
    assert client.get("/admin/services").status_code in (401, 403)


# ------------------------------------------------------------------
# GET /admin/services
# ------------------------------------------------------------------

def test_admin_list_services_includes_inactive():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    # Create one active and one inactive service
    r = client.post("/admin/services", json={
        "name": "Servicio Activo Test",
        "type": "base",
        "species": "dog",
        "is_active": True,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    active_id = r.json()["id"]

    r = client.post("/admin/services", json={
        "name": "Servicio Inactivo Test",
        "type": "base",
        "species": "dog",
        "is_active": False,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    inactive_id = r.json()["id"]

    r = client.get("/admin/services", headers=_auth(admin_token))
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert active_id in ids
    assert inactive_id in ids


def test_user_list_services_excludes_inactive():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Inactivo Para Usuario",
        "type": "base",
        "species": "dog",
        "is_active": False,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    inactive_id = r.json()["id"]

    r = client.get("/services?species=dog")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert inactive_id not in ids


# ------------------------------------------------------------------
# POST /admin/services
# ------------------------------------------------------------------

def test_create_base_service():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Baño Premium",
        "type": "base",
        "species": "dog",
        "is_active": True,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Baño Premium"
    assert data["type"] == "base"
    assert data["species"] == "dog"
    assert data["is_active"] is True
    assert "id" in data


def test_create_addon_service():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    # First create a base to use as requires
    r = client.post("/admin/services", json={
        "name": "Base Para Addon",
        "type": "base",
        "species": "cat",
        "is_active": True,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    base_id = r.json()["id"]

    r = client.post("/admin/services", json={
        "name": "Addon de Prueba",
        "type": "addon",
        "species": "cat",
        "requires": [base_id],
        "is_active": True,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    data = r.json()
    assert data["type"] == "addon"
    assert base_id in data["requires"]


def test_create_addon_without_requires_returns_422():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Addon Sin Requires",
        "type": "addon",
        "species": "dog",
    }, headers=_auth(admin_token))
    assert r.status_code == 422


def test_create_service_with_allowed_breeds():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Servicio Solo Husky",
        "type": "base",
        "species": "dog",
        "allowed_breeds": ["husky", "akita"],
        "is_active": True,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    data = r.json()
    assert set(data["allowed_breeds"]) == {"husky", "akita"}


# ------------------------------------------------------------------
# PATCH /admin/services/{id}
# ------------------------------------------------------------------

def test_update_service_name():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Nombre Original",
        "type": "base",
        "species": "dog",
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    service_id = r.json()["id"]

    r = client.patch(f"/admin/services/{service_id}", json={
        "name": "Nombre Actualizado",
    }, headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["name"] == "Nombre Actualizado"


def test_update_service_allowed_breeds():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Servicio Razas",
        "type": "base",
        "species": "dog",
        "allowed_breeds": ["husky"],
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    service_id = r.json()["id"]

    r = client.patch(f"/admin/services/{service_id}", json={
        "allowed_breeds": ["husky", "labrador", "golden"],
    }, headers=_auth(admin_token))
    assert r.status_code == 200
    assert set(r.json()["allowed_breeds"]) == {"husky", "labrador", "golden"}


def test_update_nonexistent_service_returns_404():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.patch(f"/admin/services/{uuid.uuid4()}", json={"name": "X"}, headers=_auth(admin_token))
    assert r.status_code == 404


# ------------------------------------------------------------------
# POST /admin/services/{id}/toggle
# ------------------------------------------------------------------

def test_toggle_service_deactivates_and_reactivates():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Servicio Toggle",
        "type": "base",
        "species": "dog",
        "is_active": True,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    service_id = r.json()["id"]

    r = client.post(f"/admin/services/{service_id}/toggle", json={"is_active": False}, headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    r = client.post(f"/admin/services/{service_id}/toggle", json={"is_active": True}, headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["is_active"] is True


def test_toggle_nonexistent_service_returns_404():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post(f"/admin/services/{uuid.uuid4()}/toggle", json={"is_active": False}, headers=_auth(admin_token))
    assert r.status_code == 404


# ------------------------------------------------------------------
# POST /admin/price-rules  +  GET /admin/services/{id}/price-rules
# ------------------------------------------------------------------

def test_create_price_rule_and_list():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Servicio Con Precio",
        "type": "base",
        "species": "dog",
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    service_id = r.json()["id"]

    r = client.post("/admin/price-rules", json={
        "service_id": service_id,
        "species": "dog",
        "breed_category": "mestizo",
        "weight_min": 0,
        "weight_max": 10,
        "price": 55,
        "currency": "PEN",
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    rule = r.json()
    assert rule["price"] == 55
    assert rule["breed_category"] == "mestizo"
    assert rule["service_id"] == service_id
    rule_id = rule["id"]

    r = client.get(f"/admin/services/{service_id}/price-rules", headers=_auth(admin_token))
    assert r.status_code == 200
    rule_ids = {rr["id"] for rr in r.json()}
    assert rule_id in rule_ids


def test_create_price_rule_negative_price_returns_422():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Servicio Precio Negativo",
        "type": "base",
        "species": "dog",
    }, headers=_auth(admin_token))
    service_id = r.json()["id"]

    r = client.post("/admin/price-rules", json={
        "service_id": service_id,
        "species": "dog",
        "breed_category": "mestizo",
        "weight_min": 0,
        "price": -10,
    }, headers=_auth(admin_token))
    assert r.status_code == 422


def test_create_price_rule_invalid_weight_range_returns_422():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Servicio Peso Invalido",
        "type": "base",
        "species": "dog",
    }, headers=_auth(admin_token))
    service_id = r.json()["id"]

    r = client.post("/admin/price-rules", json={
        "service_id": service_id,
        "species": "dog",
        "breed_category": "mestizo",
        "weight_min": 20,
        "weight_max": 10,
        "price": 50,
    }, headers=_auth(admin_token))
    assert r.status_code == 422


# ------------------------------------------------------------------
# PATCH /admin/price-rules/{id}
# ------------------------------------------------------------------

def test_update_price_rule():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Servicio Update Precio",
        "type": "base",
        "species": "dog",
    }, headers=_auth(admin_token))
    service_id = r.json()["id"]

    r = client.post("/admin/price-rules", json={
        "service_id": service_id,
        "species": "dog",
        "breed_category": "official",
        "weight_min": 0,
        "price": 80,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    rule_id = r.json()["id"]

    r = client.patch(f"/admin/price-rules/{rule_id}", json={"price": 95}, headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["price"] == 95


def test_deactivate_price_rule():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.post("/admin/services", json={
        "name": "Servicio Deactivar Regla",
        "type": "base",
        "species": "cat",
    }, headers=_auth(admin_token))
    service_id = r.json()["id"]

    r = client.post("/admin/price-rules", json={
        "service_id": service_id,
        "species": "cat",
        "breed_category": "mestizo",
        "weight_min": 0,
        "price": 45,
    }, headers=_auth(admin_token))
    assert r.status_code == 201
    rule_id = r.json()["id"]

    r = client.patch(f"/admin/price-rules/{rule_id}", json={"is_active": False}, headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_update_nonexistent_price_rule_returns_404():
    client = TestClient(app)
    admin_token = _register_and_login(client, role="admin")

    r = client.patch(f"/admin/price-rules/{uuid.uuid4()}", json={"price": 50}, headers=_auth(admin_token))
    assert r.status_code == 404
