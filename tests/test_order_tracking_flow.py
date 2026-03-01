"""
Tests de integración para el flujo de tracking de órdenes:
asignación de ally, transiciones de estado y control de acceso.
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app

# Distrito activo en el catálogo hardcodeado (Lima - 150101)
_DISTRICT_ID = "150101"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _register_and_login(client: TestClient, *, role: str = "user") -> tuple[str, str]:
    """Devuelve (token, user_id)."""
    email = f"tracking_{uuid.uuid4().hex}@example.com"
    r = client.post("/auth/register", json={
        "email": email,
        "password": "pass1234",
        "phone": "+51999000001",
        "first_name": "Test",
        "last_name": role.capitalize(),
        "sex": "male",
        "birth_date": "1990-01-01",
        "role": role,
    })
    assert r.status_code == 201, r.json()
    user_id = r.json()["id"]
    r = client.post("/auth/login", json={"email": email, "password": "pass1234"})
    assert r.status_code == 200
    return r.json()["access_token"], user_id


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _add_address(client: TestClient, token: str) -> str:
    """Agrega una dirección al usuario y devuelve su id."""
    r = client.post("/users/me/addresses", json={
        "district_id": _DISTRICT_ID,
        "address_line": "Av. Test 123",
        "lat": -12.046374,
        "lng": -77.042793,
        "is_default": True,
    }, headers=_auth(token))
    assert r.status_code in (200, 201), r.json()
    return r.json()["id"]


def _create_order(client: TestClient, token: str, address_id: str) -> str:
    """Crea carrito → checkout → orden. Devuelve order_id."""
    r = client.post("/cart", headers=_auth(token))
    assert r.status_code in (200, 201), r.json()
    cart_id = r.json()["id"]

    r = client.post(f"/cart/{cart_id}/items", json={
        "kind": "product", "ref_id": "p1", "qty": 1
    }, headers=_auth(token))
    assert r.status_code in (200, 201), r.json()

    r = client.post(f"/cart/{cart_id}/checkout", headers=_auth(token))
    assert r.status_code == 200, r.json()

    r = client.post("/orders", json={"cart_id": cart_id, "address_id": address_id},
                    headers=_auth(token))
    assert r.status_code in (200, 201), r.json()
    return r.json()["id"]


# ------------------------------------------------------------------
# Tests: asignación de ally (admin)
# ------------------------------------------------------------------

def test_admin_can_assign_ally_to_order():
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)
    ally_token, ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    r = client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id,
        "scheduled_at": "2030-03-07T16:00:00Z",
        "notes": "Llevar shampoo especial",
    }, headers=_auth(admin_token))
    assert r.status_code == 201, r.json()
    data = r.json()
    assert data["ally_id"] == ally_id
    assert data["order"]["ally_id"] == ally_id
    assert data["order"]["scheduled_at"] is not None


def test_non_admin_cannot_assign():
    client = TestClient(app)
    user_token, _ = _register_and_login(client)
    _, ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    r = client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id,
        "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(user_token))
    assert r.status_code == 403


def test_assign_nonexistent_order_returns_404():
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    _, ally_id = _register_and_login(client, role="ally")

    r = client.post(f"/admin/orders/00000000-0000-0000-0000-000000000000/assign", json={
        "ally_id": ally_id,
        "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(admin_token))
    assert r.status_code == 404


# ------------------------------------------------------------------
# Tests: flujo de transiciones del ally
# ------------------------------------------------------------------

def test_full_ally_flow_depart_arrive_complete():
    """Flujo completo: asignar → depart → arrive → complete."""
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)
    ally_token, ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    # Asignar ally
    r = client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id,
        "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(admin_token))
    assert r.status_code == 201

    # Ally sale hacia el domicilio
    r = client.post(f"/orders/{order_id}/depart", headers=_auth(ally_token))
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "on_the_way"

    # Ally llega, inicia servicio
    r = client.post(f"/orders/{order_id}/arrive", headers=_auth(ally_token))
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "in_service"

    # Ally termina el servicio
    r = client.post(f"/orders/{order_id}/complete", headers=_auth(ally_token))
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "done"


def test_depart_without_assignment_returns_403():
    """Un ally no puede operar una orden que no le fue asignada."""
    client = TestClient(app)
    user_token, _ = _register_and_login(client)
    ally_token, _ = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    # La orden NO fue asignada a este ally
    r = client.post(f"/orders/{order_id}/depart", headers=_auth(ally_token))
    assert r.status_code == 403


def test_ally_cannot_skip_states():
    """El ally no puede saltar de created a in_service."""
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)
    ally_token, ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id,
        "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(admin_token))

    # Intenta ir directo a arrive sin haber departado → 409
    r = client.post(f"/orders/{order_id}/arrive", headers=_auth(ally_token))
    assert r.status_code == 409


def test_complete_after_done_returns_409():
    """No se puede completar una orden ya finalizada."""
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)
    ally_token, ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id, "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(admin_token))
    client.post(f"/orders/{order_id}/depart", headers=_auth(ally_token))
    client.post(f"/orders/{order_id}/arrive", headers=_auth(ally_token))
    client.post(f"/orders/{order_id}/complete", headers=_auth(ally_token))

    r = client.post(f"/orders/{order_id}/complete", headers=_auth(ally_token))
    assert r.status_code == 409


# ------------------------------------------------------------------
# Tests: cancelación (admin)
# ------------------------------------------------------------------

def test_admin_can_cancel_created_order():
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    r = client.post(f"/admin/orders/{order_id}/cancel", headers=_auth(admin_token))
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "cancelled"


def test_admin_can_cancel_on_the_way_order():
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)
    ally_token, ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id, "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(admin_token))
    client.post(f"/orders/{order_id}/depart", headers=_auth(ally_token))

    r = client.post(f"/admin/orders/{order_id}/cancel", headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_cannot_cancel_done_order():
    """Una orden finalizada no se puede cancelar."""
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)
    ally_token, ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id, "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(admin_token))
    client.post(f"/orders/{order_id}/depart", headers=_auth(ally_token))
    client.post(f"/orders/{order_id}/arrive", headers=_auth(ally_token))
    client.post(f"/orders/{order_id}/complete", headers=_auth(ally_token))

    r = client.post(f"/admin/orders/{order_id}/cancel", headers=_auth(admin_token))
    assert r.status_code == 409


# ------------------------------------------------------------------
# Tests: listados
# ------------------------------------------------------------------

def test_ally_sees_only_own_assignments():
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)
    ally_token, ally_id = _register_and_login(client, role="ally")
    _, other_ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    # Asignar al ally (no al other_ally)
    client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id, "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(admin_token))

    r = client.get("/orders/my-assignments", headers=_auth(ally_token))
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert order_id in ids


def test_admin_list_orders_with_status_filter():
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)

    address_id = _add_address(client, user_token)
    _create_order(client, user_token, address_id)

    r = client.get("/admin/orders?status=created", headers=_auth(admin_token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert all(o["status"] == "created" for o in r.json())


def test_admin_list_orders_with_ally_filter():
    client = TestClient(app)
    admin_token, _ = _register_and_login(client, role="admin")
    user_token, _ = _register_and_login(client)
    ally_token, ally_id = _register_and_login(client, role="ally")

    address_id = _add_address(client, user_token)
    order_id = _create_order(client, user_token, address_id)

    client.post(f"/admin/orders/{order_id}/assign", json={
        "ally_id": ally_id, "scheduled_at": "2030-03-07T16:00:00Z",
    }, headers=_auth(admin_token))

    r = client.get(f"/admin/orders?ally_id={ally_id}", headers=_auth(admin_token))
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert order_id in ids
    assert all(o["ally_id"] == ally_id for o in r.json())
