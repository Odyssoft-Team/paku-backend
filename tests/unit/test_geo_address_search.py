"""Feature 0002 — búsqueda de direcciones (sin base de datos; Google simulado)."""

from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.modules.geo.api import places_router
from app.modules.geo.domain.address_search import (
    AddressProviderUnavailable,
    BiasCircle,
    PlaceDetails,
    PlaceSuggestion,
    match_district,
    normalize_text,
)
from app.modules.geo.infra.districts_data import DISTRICTS_DATA, get_all_districts
from app.modules.geo.infra.google_places import GooglePlacesProvider
from app.modules.geo.infra.memory_store import TTLCache, UsageLimiter
from app.modules.geo.use_cases.address_search import (
    AddressSearchService,
    GeoRateLimited,
    UnknownDistrict,
)

MIRAFLORES = "150122"
ATE = "150103"  # distrito inactivo


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeProvider:
    def __init__(self, *, fail: bool = False, details: Optional[PlaceDetails] = None) -> None:
        self.fail = fail
        self.details = details
        self.autocomplete_calls: list[tuple[str, Optional[BiasCircle], Optional[str]]] = []
        self.details_calls = 0
        self.geocode_calls: list[str] = []

    async def autocomplete(self, query, *, bias, session_token):
        if self.fail:
            raise AddressProviderUnavailable()
        self.autocomplete_calls.append((query, bias, session_token))
        return [PlaceSuggestion(place_id="p1", main_text=f"{query} 123", secondary_text="Miraflores, Lima")]

    async def place_details(self, place_id, *, session_token):
        if self.fail:
            raise AddressProviderUnavailable()
        self.details_calls += 1
        return self.details

    async def geocode(self, address):
        if self.fail:
            raise AddressProviderUnavailable()
        self.geocode_calls.append(address)
        return (-12.12, -77.03)


def make_service(provider, *, per_minute=60, per_day=300, lookups=30, clock=None):
    clock = clock or FakeClock()
    return AddressSearchService(
        provider=provider,
        districts=get_all_districts(active_only=False),
        cache=TTLCache(ttl_seconds=86400, clock=clock),
        autocomplete_per_minute=UsageLimiter(limit=per_minute, window_seconds=60, clock=clock),
        autocomplete_per_day=UsageLimiter(limit=per_day, window_seconds=86400, clock=clock),
        lookups_per_day=UsageLimiter(limit=lookups, window_seconds=86400, clock=clock),
    )


# ─── Reglas puras ─────────────────────────────────────────────────────────────


def test_all_districts_have_coordinates():
    assert len(DISTRICTS_DATA) == 43
    for d in DISTRICTS_DATA:
        assert -13 < d["lat"] < -11 and -78 < d["lng"] < -76, d["name"]


def test_normalize_text_ignores_accents_case_and_spaces():
    assert normalize_text("  Av.  Javier   PRADO ") == "av. javier prado"
    assert normalize_text("Jesús María") == "jesus maria"


def test_match_district_by_name_prefix_and_alias():
    districts = get_all_districts(active_only=False)
    assert match_district(["Distrito de Miraflores"], districts)["id"] == MIRAFLORES
    assert match_district(["JESUS MARIA"], districts)["id"] == "150113"
    assert match_district(["Cercado de Lima"], districts)["id"] == "150101"
    assert match_district(["Provincia de Lima", "Miraflores"], districts)["id"] == "150101"
    assert match_district(["Arequipa"], districts) is None


# ─── Servicio ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_autocomplete_short_query_does_not_call_provider():
    provider = FakeProvider()
    service = make_service(provider)
    assert await service.autocomplete(user_id="u", query=" av ", district_id=MIRAFLORES, session_token=None) == []
    assert provider.autocomplete_calls == []


@pytest.mark.asyncio
async def test_autocomplete_biases_to_district_and_caches():
    provider = FakeProvider()
    service = make_service(provider)
    first = await service.autocomplete(user_id="u", query="Av Larco", district_id=MIRAFLORES, session_token="s1")
    again = await service.autocomplete(user_id="u2", query="  av  LARCO ", district_id=MIRAFLORES, session_token="s2")
    assert first == again
    assert len(provider.autocomplete_calls) == 1  # el segundo salió del cache
    query, bias, token = provider.autocomplete_calls[0]
    assert query == "Av Larco" and token == "s1"
    assert bias is not None and round(bias.lat, 2) == -12.12


@pytest.mark.asyncio
async def test_autocomplete_unknown_district():
    service = make_service(FakeProvider())
    with pytest.raises(UnknownDistrict):
        await service.autocomplete(user_id="u", query="Av Larco", district_id="999", session_token=None)


@pytest.mark.asyncio
async def test_autocomplete_rate_limit_per_minute_resets():
    clock = FakeClock()
    service = make_service(FakeProvider(), per_minute=2, clock=clock)
    await service.autocomplete(user_id="u", query="calle uno", district_id=None, session_token=None)
    await service.autocomplete(user_id="u", query="calle dos", district_id=None, session_token=None)
    with pytest.raises(GeoRateLimited):
        await service.autocomplete(user_id="u", query="calle tres", district_id=None, session_token=None)
    # Otro usuario no se ve afectado
    await service.autocomplete(user_id="otro", query="calle tres", district_id=None, session_token=None)
    clock.now += 61
    await service.autocomplete(user_id="u", query="calle cuatro", district_id=None, session_token=None)


@pytest.mark.asyncio
async def test_place_details_matches_district_and_caches():
    provider = FakeProvider(
        details=PlaceDetails(
            lat=-12.121,
            lng=-77.029,
            formatted_address="Av. José Larco 345, Miraflores 15074, Perú",
            address_line="Avenida José Larco",
            building_number="345",
            area_names=["Miraflores", "Provincia de Lima"],
        )
    )
    service = make_service(provider)
    place = await service.place_details(user_id="u", place_id="p1", session_token="s1")
    assert place.district_id == MIRAFLORES and place.district_active is True
    assert place.address_line == "Avenida José Larco" and place.building_number == "345"
    await service.place_details(user_id="u", place_id="p1", session_token="s1")
    assert provider.details_calls == 1


@pytest.mark.asyncio
async def test_place_details_inactive_district_is_reported():
    provider = FakeProvider(details=PlaceDetails(lat=-12.04, lng=-76.9, area_names=["Ate"]))
    place = await make_service(provider).place_details(user_id="u", place_id="p2", session_token=None)
    assert place.district_id == ATE and place.district_active is False


@pytest.mark.asyncio
async def test_lookup_limit_covers_details_and_geocode():
    service = make_service(FakeProvider(details=PlaceDetails(lat=1, lng=1)), lookups=2)
    await service.place_details(user_id="u", place_id="a", session_token=None)
    await service.geocode(user_id="u", query="Av Larco 345", district_id=MIRAFLORES)
    with pytest.raises(GeoRateLimited):
        await service.place_details(user_id="u", place_id="b", session_token=None)


@pytest.mark.asyncio
async def test_geocode_adds_district_and_city():
    provider = FakeProvider()
    result = await make_service(provider).geocode(user_id="u", query="Av Larco 345", district_id=MIRAFLORES)
    assert result == (-12.12, -77.03)
    assert provider.geocode_calls == ["Av Larco 345, Miraflores, Lima, Perú"]


def test_ttl_cache_expires():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=10, clock=clock)
    cache.set("k", 1)
    assert cache.get("k") == 1
    clock.now += 11
    assert cache.get("k") is None


# ─── Proveedor Google (HTTP simulado) ─────────────────────────────────────────


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_google_autocomplete_request_and_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("X-Goog-Api-Key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "suggestions": [
                    {
                        "placePrediction": {
                            "placeId": "abc",
                            "text": {"text": "Av. José Larco, Miraflores"},
                            "structuredFormat": {
                                "mainText": {"text": "Av. José Larco"},
                                "secondaryText": {"text": "Miraflores, Perú"},
                            },
                        }
                    },
                    {"queryPrediction": {"text": {"text": "larco"}}},
                ]
            },
        )

    provider = GooglePlacesProvider("KEY", transport=_transport(handler))
    items = await provider.autocomplete("larco", bias=BiasCircle(lat=-12.12, lng=-77.03), session_token="tok")
    assert items == [PlaceSuggestion(place_id="abc", main_text="Av. José Larco", secondary_text="Miraflores, Perú")]
    assert seen["url"].endswith("/v1/places:autocomplete") and seen["key"] == "KEY"
    assert seen["body"]["includedRegionCodes"] == ["pe"]
    assert seen["body"]["sessionToken"] == "tok"
    assert seen["body"]["locationBias"]["circle"]["radius"] == 3000.0


@pytest.mark.asyncio
async def test_google_details_uses_minimal_field_mask():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["mask"] = request.headers.get("X-Goog-FieldMask")
        return httpx.Response(
            200,
            json={
                "formattedAddress": "Av. José Larco 345, Miraflores, Perú",
                "location": {"latitude": -12.121, "longitude": -77.029},
                "addressComponents": [
                    {"longText": "345", "types": ["street_number"]},
                    {"longText": "Avenida José Larco", "types": ["route"]},
                    {"longText": "Miraflores", "types": ["locality", "political"]},
                    {"longText": "Provincia de Lima", "types": ["administrative_area_level_2"]},
                ],
            },
        )

    provider = GooglePlacesProvider("KEY", transport=_transport(handler))
    details = await provider.place_details("abc", session_token="tok")
    assert seen["mask"] == "addressComponents,location,formattedAddress"
    assert details.building_number == "345" and details.address_line == "Avenida José Larco"
    assert details.area_names == ["Miraflores", "Provincia de Lima"]


@pytest.mark.asyncio
async def test_google_errors_become_unavailable():
    provider = GooglePlacesProvider("KEY", transport=_transport(lambda r: httpx.Response(403, json={})))
    with pytest.raises(AddressProviderUnavailable):
        await provider.autocomplete("larco", bias=None, session_token=None)

    denied = GooglePlacesProvider(
        "KEY", transport=_transport(lambda r: httpx.Response(200, json={"status": "REQUEST_DENIED"}))
    )
    with pytest.raises(AddressProviderUnavailable):
        await denied.geocode("Av Larco 345, Lima, Perú")

    empty = GooglePlacesProvider("KEY", transport=_transport(lambda r: httpx.Response(200, json={"status": "ZERO_RESULTS"})))
    assert await empty.geocode("xxxx") is None


# ─── Endpoints ────────────────────────────────────────────────────────────────


def _client(service, monkeypatch, *, key: Optional[str] = "KEY") -> TestClient:
    app = FastAPI()
    app.include_router(places_router.router, prefix="/geo")
    user = CurrentUser(id=uuid4(), email="u@paku.pe", role="user", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(places_router.settings, "GOOGLE_PLACES_API_KEY", key)
    monkeypatch.setattr(places_router, "_service", service)
    return TestClient(app)


def test_endpoint_autocomplete_ok(monkeypatch):
    client = _client(make_service(FakeProvider()), monkeypatch)
    resp = client.get("/geo/places/autocomplete", params={"q": "Av Larco", "district_id": MIRAFLORES})
    assert resp.status_code == 200
    assert resp.json() == [{"place_id": "p1", "main_text": "Av Larco 123", "secondary_text": "Miraflores, Lima"}]


def test_endpoint_without_key_returns_503(monkeypatch):
    client = _client(None, monkeypatch, key=None)
    resp = client.get("/geo/places/autocomplete", params={"q": "Av Larco"})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "GEO_UNAVAILABLE"


def test_endpoint_provider_down_returns_503(monkeypatch):
    client = _client(make_service(FakeProvider(fail=True)), monkeypatch)
    assert client.get("/geo/geocode", params={"q": "Av Larco 345"}).status_code == 503


def test_endpoint_rate_limited_returns_429(monkeypatch):
    client = _client(make_service(FakeProvider(), per_minute=1), monkeypatch)
    assert client.get("/geo/places/autocomplete", params={"q": "calle uno"}).status_code == 200
    resp = client.get("/geo/places/autocomplete", params={"q": "calle dos"})
    assert resp.status_code == 429 and resp.json()["detail"]["code"] == "GEO_RATE_LIMITED"


def test_endpoint_details_not_found_and_unknown_district(monkeypatch):
    client = _client(make_service(FakeProvider(details=None)), monkeypatch)
    assert client.get("/geo/places/xyz").status_code == 404
    assert client.get("/geo/places/autocomplete", params={"q": "Av Larco", "district_id": "999"}).status_code == 422


def test_endpoint_requires_auth(monkeypatch):
    app = FastAPI()
    app.include_router(places_router.router, prefix="/geo")
    monkeypatch.setattr(places_router.settings, "GOOGLE_PLACES_API_KEY", "KEY")
    resp = TestClient(app).get("/geo/places/autocomplete", params={"q": "Av Larco"})
    assert resp.status_code in (401, 403)
