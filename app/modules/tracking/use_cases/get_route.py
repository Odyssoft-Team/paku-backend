"""
Use case: obtener polyline, ETA y distancia via Google Routes API.

Comportamiento:
  - Si GOOGLE_ROUTES_API_KEY no está configurada → HTTP 501 (no implementado).
  - Si el ally aún no reportó posición → devuelve RouteOut con campos None
    (el frontend muestra el destino sin ruta trazada).
  - Si Google Routes falla → HTTP 502 con detalle del error.

Google Routes API (v2):
  POST https://routes.googleapis.com/directions/v2:computeRoutes
  Header: X-Goog-Api-Key: <key>
  Header: X-Goog-FieldMask: routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.core.settings import settings
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.tracking.domain.location import (
    AllyLocation,
    assert_can_read,
    assert_tracking_readable,
)
from app.modules.tracking.infra.location_store import location_store
from app.modules.tracking.use_cases.get_current import _extract_destination

logger = logging.getLogger(__name__)

_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
_FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"


def _seconds_to_display(seconds: int) -> str:
    """Convierte segundos a string legible. Ej: 420 → '7 min', 3700 → '1 h 2 min'."""
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, remaining = divmod(minutes, 60)
    return f"{hours} h {remaining} min" if remaining else f"{hours} h"


async def _call_google_routes(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> dict[str, Any]:
    """Llama a Google Routes API y devuelve el primer route o lanza HTTPException."""
    body = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    headers = {
        "X-Goog-Api-Key": settings.GOOGLE_ROUTES_API_KEY,
        "X-Goog-FieldMask": _FIELD_MASK,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(_ROUTES_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Google Routes API error: %s %s", exc.response.status_code, exc.response.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="routes_api_error: Google Routes returned an error",
        ) from exc
    except Exception as exc:
        logger.error("Google Routes API unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="routes_api_error: could not reach Google Routes API",
        ) from exc

    routes = data.get("routes", [])
    if not routes:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="routes_api_error: no routes returned by Google",
        )
    return routes[0]


@dataclass
class GetRoute:
    orders_repo: PostgresOrderRepository

    async def execute(
        self,
        *,
        order_id: UUID,
        requester_id: UUID,
        requester_role: str,
    ) -> dict[str, Any]:
        """
        Devuelve un dict con las claves:
          order_id, ally_location (AllyLocation | None), destination (dict),
          eta_seconds, eta_display, polyline, distance_meters
        """
        # Prerequisito: API key configurada
        if not settings.GOOGLE_ROUTES_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="routes_not_configured: GOOGLE_ROUTES_API_KEY is not set",
            )

        # 1. Leer orden
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        # 2. Tracking legible
        try:
            assert_tracking_readable(order)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        # 3. Acceso
        try:
            assert_can_read(order, requester_id, requester_role)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

        # 4. Destino
        destination = _extract_destination(order)

        # 5. Posición del ally (puede ser None)
        ally_location: AllyLocation | None = location_store.get(order_id)

        # Sin origen conocido: devolvemos destino sin ruta
        if ally_location is None:
            return {
                "order_id": order_id,
                "ally_location": None,
                "destination": destination,
                "eta_seconds": None,
                "eta_display": None,
                "polyline": None,
                "distance_meters": None,
            }

        # 6. Llamar a Google Routes
        route = await _call_google_routes(
            origin_lat=ally_location.lat,
            origin_lng=ally_location.lng,
            dest_lat=destination["lat"],
            dest_lng=destination["lng"],
        )

        duration_str: str = route.get("duration", "0s")
        # duration viene como "420s" → extraer entero
        try:
            eta_seconds = int(duration_str.rstrip("s"))
        except ValueError:
            eta_seconds = None

        distance_meters: int | None = route.get("distanceMeters")
        polyline: str | None = route.get("polyline", {}).get("encodedPolyline")
        eta_display = _seconds_to_display(eta_seconds) if eta_seconds is not None else None

        return {
            "order_id": order_id,
            "ally_location": ally_location,
            "destination": destination,
            "eta_seconds": eta_seconds,
            "eta_display": eta_display,
            "polyline": polyline,
            "distance_meters": distance_meters,
        }
