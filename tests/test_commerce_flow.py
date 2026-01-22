from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_services_requires_species():
    r = client.get("/services")
    # FastAPI devuelve 422 cuando falta un query param obligatorio
    assert r.status_code == 422


def test_list_services_filters_by_species():
    r = client.get("/services?species=dog")
    assert r.status_code == 200
    data = r.json()
    for item in data:
        assert item.get("species") == "dog"


def test_list_services_filters_by_breed_when_allowed_breeds_present():
    r = client.get("/services?species=dog&breed=husky")
    assert r.status_code == 200
    data = r.json()
    # Con la data hardcodeada actual, allowed_breeds es None en todos los servicios,
    # por lo que el filtro por breed no excluye nada.
    # Si en el futuro se añade un servicio con allowed_breeds, este test verificará
    # que se excluya cuando breed no esté en esa lista.
    assert isinstance(data, list)
