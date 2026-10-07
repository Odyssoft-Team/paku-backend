"""Proveedor de direcciones con Google (feature 0002).

- Autocomplete: Places API (New) `places:autocomplete`, restringido a Perú y con
  `sessionToken` para que Google cobre la búsqueda como una sesión.
- Detalle: Places API (New) `places/{id}` con field mask mínima
  (`addressComponents,location,formattedAddress` → tarifa Essentials).
- Geocode: Geocoding API, solo como respaldo cuando no se eligió sugerencia.

Cualquier falla de red, clave rechazada o falta de cuota se traduce en
`AddressProviderUnavailable` (el endpoint responde 503 y la app sigue sin sugerencias).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.modules.geo.domain.address_search import (
    MAX_SUGGESTIONS,
    AddressProviderUnavailable,
    BiasCircle,
    PlaceDetails,
    PlaceSuggestion,
)

logger = logging.getLogger(__name__)

_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
_DETAILS_FIELD_MASK = "addressComponents,location,formattedAddress"
_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_TIMEOUT = 6.0

# Tipos de componente de Google que pueden traer el distrito (del más específico al más general)
_AREA_TYPES = (
    "sublocality_level_1",
    "sublocality",
    "locality",
    "administrative_area_level_3",
    "administrative_area_level_2",
)


class GooglePlacesProvider:
    def __init__(self, api_key: str, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._key = api_key
        self._transport = transport  # inyectable en tests

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport)

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with self._client() as client:
                resp = await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            logger.error("Google geo inalcanzable: %s", exc)
            raise AddressProviderUnavailable() from exc
        if resp.status_code >= 400:
            logger.error("Google geo error %s: %s", resp.status_code, resp.text[:300])
            raise AddressProviderUnavailable()
        try:
            return resp.json()
        except ValueError as exc:
            raise AddressProviderUnavailable() from exc

    async def autocomplete(
        self, query: str, *, bias: Optional[BiasCircle], session_token: Optional[str]
    ) -> list[PlaceSuggestion]:
        body: dict[str, Any] = {
            "input": query,
            "includedRegionCodes": ["pe"],
            "languageCode": "es",
        }
        if bias is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": bias.lat, "longitude": bias.lng},
                    "radius": bias.radius_m,
                }
            }
        if session_token:
            body["sessionToken"] = session_token
        data = await self._request("POST", _AUTOCOMPLETE_URL, json=body, headers={"X-Goog-Api-Key": self._key})

        suggestions: list[PlaceSuggestion] = []
        for item in data.get("suggestions", []):
            prediction = item.get("placePrediction")
            if not prediction or not prediction.get("placeId"):
                continue
            structured = prediction.get("structuredFormat") or {}
            main = (structured.get("mainText") or {}).get("text") or (prediction.get("text") or {}).get("text")
            if not main:
                continue
            secondary = (structured.get("secondaryText") or {}).get("text")
            suggestions.append(PlaceSuggestion(place_id=prediction["placeId"], main_text=main, secondary_text=secondary))
            if len(suggestions) >= MAX_SUGGESTIONS:
                break
        return suggestions

    async def place_details(self, place_id: str, *, session_token: Optional[str]) -> Optional[PlaceDetails]:
        params: dict[str, str] = {"languageCode": "es"}
        if session_token:
            params["sessionToken"] = session_token
        try:
            async with self._client() as client:
                resp = await client.get(
                    _DETAILS_URL.format(place_id=place_id),
                    params=params,
                    headers={"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": _DETAILS_FIELD_MASK},
                )
        except httpx.HTTPError as exc:
            logger.error("Google Place Details inalcanzable: %s", exc)
            raise AddressProviderUnavailable() from exc
        if resp.status_code in (400, 404):
            return None  # place_id inválido o vencido
        if resp.status_code >= 400:
            logger.error("Google Place Details error %s: %s", resp.status_code, resp.text[:300])
            raise AddressProviderUnavailable()
        data = resp.json()

        location = data.get("location") or {}
        if "latitude" not in location or "longitude" not in location:
            return None

        by_type: dict[str, str] = {}
        for comp in data.get("addressComponents", []):
            text = comp.get("longText") or comp.get("shortText")
            for t in comp.get("types", []):
                by_type.setdefault(t, text)

        return PlaceDetails(
            lat=float(location["latitude"]),
            lng=float(location["longitude"]),
            formatted_address=data.get("formattedAddress"),
            address_line=by_type.get("route"),
            building_number=by_type.get("street_number"),
            area_names=[by_type[t] for t in _AREA_TYPES if by_type.get(t)],
        )

    async def geocode(self, address: str) -> Optional[tuple[float, float]]:
        data = await self._request(
            "GET",
            _GEOCODE_URL,
            params={"address": address, "components": "country:PE", "language": "es", "key": self._key},
        )
        status = data.get("status")
        if status == "ZERO_RESULTS":
            return None
        if status != "OK":
            # OVER_QUERY_LIMIT, REQUEST_DENIED, etc.
            logger.error("Google Geocoding status %s: %s", status, data.get("error_message"))
            raise AddressProviderUnavailable()
        results = data.get("results") or []
        if not results:
            return None
        loc = results[0].get("geometry", {}).get("location", {})
        if "lat" not in loc or "lng" not in loc:
            return None
        return float(loc["lat"]), float(loc["lng"])
