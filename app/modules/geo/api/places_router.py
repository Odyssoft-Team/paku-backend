"""Endpoints de búsqueda de direcciones (feature 0002).

Router aparte del de distritos: no depende de la base de datos y el proveedor
externo (Google) solo se usa si `GOOGLE_PLACES_API_KEY` está configurada.

- GET /geo/places/autocomplete  → sugerencias de calles (desde 3 letras)
- GET /geo/places/{place_id}     → calle, número, coordenadas y distrito
- GET /geo/geocode               → coordenadas de un texto (respaldo)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.auth import CurrentUser, get_current_user
from app.core.settings import settings
from app.modules.geo.domain.address_search import AddressProviderUnavailable
from app.modules.geo.infra.districts_data import get_all_districts
from app.modules.geo.infra.google_places import GooglePlacesProvider
from app.modules.geo.infra.memory_store import TTLCache, UsageLimiter
from app.modules.geo.use_cases.address_search import (
    AddressSearchService,
    GeoRateLimited,
    UnknownDistrict,
)

router = APIRouter(tags=["geo"])


# ─── Contratos ────────────────────────────────────────────────────────────────


class PlaceSuggestionOut(BaseModel):
    place_id: str
    main_text: str
    secondary_text: Optional[str] = None


class PlaceDetailsOut(BaseModel):
    place_id: str
    lat: float
    lng: float
    formatted_address: Optional[str] = None
    address_line: Optional[str] = None
    building_number: Optional[str] = None
    # Distrito de nuestro catálogo que coincide con la dirección (null si ninguno)
    district_id: Optional[str] = None
    district_name: Optional[str] = None
    # False si el distrito existe pero Paku aún no atiende ahí
    district_active: Optional[bool] = None


class GeocodeOut(BaseModel):
    lat: float
    lng: float


# ─── Servicio (una instancia por proceso: el cache y los límites viven en memoria) ──

_service: Optional[AddressSearchService] = None


def _build_service(api_key: str) -> AddressSearchService:
    return AddressSearchService(
        provider=GooglePlacesProvider(api_key),
        districts=get_all_districts(active_only=False),
        cache=TTLCache(ttl_seconds=settings.GEO_CACHE_TTL_SECONDS),
        autocomplete_per_minute=UsageLimiter(limit=settings.GEO_AUTOCOMPLETE_PER_MINUTE, window_seconds=60),
        autocomplete_per_day=UsageLimiter(limit=settings.GEO_AUTOCOMPLETE_PER_DAY, window_seconds=86400),
        lookups_per_day=UsageLimiter(limit=settings.GEO_LOOKUP_PER_DAY, window_seconds=86400),
    )


def get_address_search_service() -> AddressSearchService:
    global _service
    if not settings.GOOGLE_PLACES_API_KEY:
        raise _unavailable()
    if _service is None:
        _service = _build_service(settings.GOOGLE_PLACES_API_KEY)
    return _service


# ─── Errores ──────────────────────────────────────────────────────────────────


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "GEO_UNAVAILABLE", "message": "La búsqueda de direcciones no está disponible."},
    )


def _rate_limited() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "GEO_RATE_LIMITED", "message": "Demasiadas búsquedas. Intenta más tarde."},
    )


def _unknown_district() -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": "DISTRICT_NOT_FOUND", "message": "El distrito no existe."},
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/places/autocomplete", response_model=list[PlaceSuggestionOut])
async def autocomplete_places(
    q: str = Query(..., max_length=120, description="Texto escrito; menos de 3 letras devuelve []"),
    district_id: Optional[str] = Query(default=None, description="Distrito elegido: centra la búsqueda"),
    session_token: Optional[str] = Query(default=None, max_length=64),
    current: CurrentUser = Depends(get_current_user),
    service: AddressSearchService = Depends(get_address_search_service),
) -> list[PlaceSuggestionOut]:
    try:
        items = await service.autocomplete(
            user_id=str(current.id), query=q, district_id=district_id, session_token=session_token
        )
    except UnknownDistrict:
        raise _unknown_district()
    except GeoRateLimited:
        raise _rate_limited()
    except AddressProviderUnavailable:
        raise _unavailable()
    return [PlaceSuggestionOut(place_id=i.place_id, main_text=i.main_text, secondary_text=i.secondary_text) for i in items]


@router.get("/places/{place_id}", response_model=PlaceDetailsOut)
async def get_place(
    place_id: str,
    session_token: Optional[str] = Query(default=None, max_length=64),
    current: CurrentUser = Depends(get_current_user),
    service: AddressSearchService = Depends(get_address_search_service),
) -> PlaceDetailsOut:
    try:
        place = await service.place_details(user_id=str(current.id), place_id=place_id, session_token=session_token)
    except GeoRateLimited:
        raise _rate_limited()
    except AddressProviderUnavailable:
        raise _unavailable()
    if place is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GEO_NOT_FOUND", "message": "No se encontró la dirección."},
        )
    return PlaceDetailsOut(**place.__dict__)


@router.get("/geocode", response_model=GeocodeOut)
async def geocode_address(
    q: str = Query(..., min_length=1, max_length=200, description="Dirección escrita (calle y número)"),
    district_id: Optional[str] = Query(default=None),
    current: CurrentUser = Depends(get_current_user),
    service: AddressSearchService = Depends(get_address_search_service),
) -> GeocodeOut:
    try:
        result = await service.geocode(user_id=str(current.id), query=q, district_id=district_id)
    except UnknownDistrict:
        raise _unknown_district()
    except GeoRateLimited:
        raise _rate_limited()
    except AddressProviderUnavailable:
        raise _unavailable()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GEO_NOT_FOUND", "message": "No se encontró la dirección."},
        )
    return GeocodeOut(lat=result[0], lng=result[1])
