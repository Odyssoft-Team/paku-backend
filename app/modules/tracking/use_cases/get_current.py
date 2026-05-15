"""
Use case: obtener la última posición conocida del ally y el destino del servicio.

Flujo:
  1. Lee la orden.
  2. Valida que el tracking está disponible para lectura.
  3. Valida que el requester tiene acceso (dueño / ally asignado / admin).
  4. Lee la última posición del LocationStore (puede ser None si el ally aún no reportó).
  5. Extrae el destino del delivery_address_snapshot de la orden.
  6. Calcula staleness_seconds.
  7. Devuelve los datos para CurrentLocationOut.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.domain.order import Order
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.tracking.domain.location import (
    AllyLocation,
    assert_can_read,
    assert_tracking_readable,
)
from app.modules.tracking.infra.postgres_location_store import PostgresLocationStore


def _extract_destination(order: Order) -> dict[str, Any]:
    """
    Extrae lat/lng del delivery_address_snapshot de la orden.
    Lanza HTTPException 422 si la orden no tiene dirección de entrega con coordenadas.
    """
    snapshot = order.delivery_address_snapshot
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tracking_no_destination: order has no delivery address snapshot",
        )
    lat = snapshot.get("lat")
    lng = snapshot.get("lng")
    if lat is None or lng is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tracking_no_destination: delivery address snapshot has no lat/lng",
        )
    return {"lat": float(lat), "lng": float(lng)}


@dataclass
class GetCurrent:
    orders_repo: PostgresOrderRepository
    location_store: PostgresLocationStore

    async def execute(
        self,
        *,
        order_id: UUID,
        requester_id: UUID,
        requester_role: str,
    ) -> dict[str, Any]:
        """
        Devuelve un dict con las claves:
          order_id, order_status, ally_location (AllyLocation | None),
          destination (dict lat/lng), staleness_seconds (int | None)
        """
        # 1. Leer orden
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        # 2. Tracking debe estar disponible para lectura
        try:
            assert_tracking_readable(order)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        # 3. Verificar acceso
        try:
            assert_can_read(order, requester_id, requester_role)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

        # 4. Última posición del ally desde PostgreSQL (puede ser None)
        ally_location: AllyLocation | None = await self.location_store.get(order_id)

        # 5. Destino
        destination = _extract_destination(order)

        # 6. Antigüedad de los datos
        staleness_seconds: int | None = None
        if ally_location is not None:
            delta = datetime.now(timezone.utc) - ally_location.recorded_at
            staleness_seconds = int(delta.total_seconds())

        return {
            "order_id": order_id,
            "order_status": order.status.value,
            "ally_location": ally_location,
            "destination": destination,
            "staleness_seconds": staleness_seconds,
        }
