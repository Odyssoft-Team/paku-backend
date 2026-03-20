"""
Schemas Pydantic del módulo tracking.

Contratos de request/response para los tres endpoints:
  - POST /tracking/orders/{order_id}/location  (ally reporta posición)
  - GET  /tracking/orders/{order_id}/current   (última posición + destino)
  - GET  /tracking/orders/{order_id}/route     (polyline + ETA via Google Routes)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Entrada — reporte de posición del ally
# ---------------------------------------------------------------------------

class ReportLocationIn(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitud WGS-84")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitud WGS-84")
    accuracy_m: Optional[float] = Field(
        None, ge=0.0, le=5000.0,
        description="Precisión del GPS en metros (opcional, viene del SDK móvil)"
    )


# ---------------------------------------------------------------------------
# Fragmento reutilizable — un punto geográfico con metadatos
# ---------------------------------------------------------------------------

class LocationPoint(BaseModel):
    lat: float
    lng: float
    accuracy_m: Optional[float] = None
    recorded_at: Optional[datetime] = None   # None cuando es el destino fijo


# ---------------------------------------------------------------------------
# Respuestas
# ---------------------------------------------------------------------------

class ReportLocationOut(BaseModel):
    """Confirmación de que la posición fue recibida y almacenada."""
    order_id: UUID
    lat: float
    lng: float
    recorded_at: datetime


class CurrentLocationOut(BaseModel):
    """
    Última posición conocida del ally + destino del servicio.

    - ally_location es None si el ally aún no ha reportado ninguna posición
      (acaba de cambiar el estado a on_the_way pero no envió GPS todavía).
    - staleness_seconds indica cuántos segundos tienen los datos de ally_location.
      El frontend puede usarlo para mostrar un aviso de "datos desactualizados"
      si supera, por ejemplo, 30 segundos.
    """
    order_id: UUID
    order_status: str
    ally_location: Optional[LocationPoint]
    destination: LocationPoint
    staleness_seconds: Optional[int]         # None si ally_location es None


class RouteOut(BaseModel):
    """
    Información de ruta y ETA calculada por Google Routes API.

    - Todos los campos opcionales pueden ser None si:
        a) El ally aún no reportó posición (no hay origen).
        b) Google Routes devolvió error o no hay API key configurada.
    """
    order_id: UUID
    ally_location: Optional[LocationPoint]
    destination: LocationPoint
    eta_seconds: Optional[int]
    eta_display: Optional[str]               # e.g. "7 min" para mostrar en UI
    polyline: Optional[str]                  # encoded polyline para Google Maps SDK
    distance_meters: Optional[int]
