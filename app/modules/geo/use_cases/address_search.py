"""Caso de uso: búsqueda de direcciones con control de gasto (feature 0002).

Reglas:
- Autocomplete solo desde `MIN_QUERY_LENGTH` letras; con menos responde vacío sin
  llamar al proveedor.
- Cache por (texto normalizado, distrito) y por place_id; un acierto de cache no
  llama al proveedor.
- Límite por usuario: autocomplete por minuto y por día; detalle + geocode por día.
- El distrito elegido centra la búsqueda (sesgo, no restricción): una avenida
  puede cruzar distritos y el detalle devuelve el distrito real.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.modules.geo.domain.address_search import (
    MIN_QUERY_LENGTH,
    AddressProvider,
    BiasCircle,
    PlaceSuggestion,
    match_district,
    normalize_text,
)
from app.modules.geo.infra.memory_store import TTLCache, UsageLimiter


class GeoRateLimited(Exception):
    """El usuario superó su límite de búsquedas."""


class UnknownDistrict(Exception):
    """El district_id no existe en el catálogo."""


@dataclass(frozen=True)
class ResolvedPlace:
    place_id: str
    lat: float
    lng: float
    formatted_address: Optional[str]
    address_line: Optional[str]
    building_number: Optional[str]
    district_id: Optional[str]
    district_name: Optional[str]
    district_active: Optional[bool]


class AddressSearchService:
    def __init__(
        self,
        *,
        provider: AddressProvider,
        districts: list[dict],
        cache: TTLCache,
        autocomplete_per_minute: UsageLimiter,
        autocomplete_per_day: UsageLimiter,
        lookups_per_day: UsageLimiter,
    ) -> None:
        self._provider = provider
        self._districts = districts
        self._districts_by_id = {d["id"]: d for d in districts}
        self._cache = cache
        self._ac_minute = autocomplete_per_minute
        self._ac_day = autocomplete_per_day
        self._lookups_day = lookups_per_day

    def _district(self, district_id: Optional[str]) -> Optional[dict]:
        if not district_id:
            return None
        district = self._districts_by_id.get(district_id)
        if district is None:
            raise UnknownDistrict()
        return district

    async def autocomplete(
        self,
        *,
        user_id: str,
        query: str,
        district_id: Optional[str],
        session_token: Optional[str],
    ) -> list[PlaceSuggestion]:
        district = self._district(district_id)
        text = " ".join(query.split())
        if len(text) < MIN_QUERY_LENGTH:
            return []

        cache_key = ("ac", normalize_text(text), district_id or "")
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not (self._ac_minute.hit(user_id) and self._ac_day.hit(user_id)):
            raise GeoRateLimited()

        bias = None
        if district is not None and district.get("lat") is not None:
            bias = BiasCircle(lat=district["lat"], lng=district["lng"])
        suggestions = await self._provider.autocomplete(text, bias=bias, session_token=session_token)
        self._cache.set(cache_key, suggestions)
        return suggestions

    async def place_details(
        self, *, user_id: str, place_id: str, session_token: Optional[str]
    ) -> Optional[ResolvedPlace]:
        cache_key = ("pd", place_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not self._lookups_day.hit(user_id):
            raise GeoRateLimited()

        details = await self._provider.place_details(place_id, session_token=session_token)
        if details is None:
            return None
        district = match_district(details.area_names, self._districts)
        resolved = ResolvedPlace(
            place_id=place_id,
            lat=details.lat,
            lng=details.lng,
            formatted_address=details.formatted_address,
            address_line=details.address_line,
            building_number=details.building_number,
            district_id=district["id"] if district else None,
            district_name=district["name"] if district else None,
            district_active=bool(district.get("active")) if district else None,
        )
        self._cache.set(cache_key, resolved)
        return resolved

    async def geocode(
        self, *, user_id: str, query: str, district_id: Optional[str]
    ) -> Optional[tuple[float, float]]:
        district = self._district(district_id)
        text = " ".join(query.split())
        if not text:
            return None
        area = f", {district['name']}" if district else ""
        address = f"{text}{area}, Lima, Perú"

        cache_key = ("gc", normalize_text(address))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not self._lookups_day.hit(user_id):
            raise GeoRateLimited()

        result = await self._provider.geocode(address)
        if result is not None:
            self._cache.set(cache_key, result)
        return result
