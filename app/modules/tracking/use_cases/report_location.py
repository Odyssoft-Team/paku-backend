"""
Use case: el groomer reporta su posición actual.

Flujo:
  1. Lee la orden (sin restricción de user_id, igual que streaming).
  2. Valida que el tracking está abierto para escritura (on_the_way o in_service).
  3. Valida que el requester es el groomer asignado a esa orden.
  4. Almacena la posición en el LocationStore (en memoria).
  5. Devuelve la GroomerLocation guardada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.tracking.domain.location import (
    GroomerLocation,
    assert_is_groomer,
    assert_tracking_writable,
)
from app.modules.tracking.infra.postgres_location_store import PostgresLocationStore


@dataclass
class ReportLocation:
    orders_repo: PostgresOrderRepository
    location_store: PostgresLocationStore

    async def execute(
        self,
        *,
        order_id: UUID,
        groomer_id: UUID,
        lat: float,
        lng: float,
        accuracy_m: float | None,
    ) -> GroomerLocation:
        # 1. Leer orden (admin-level: sin filtro por user_id)
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        # 2. Tracking debe estar abierto para escritura
        try:
            assert_tracking_writable(order)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        # 3. Solo el groomer asignado puede reportar posición
        try:
            assert_is_groomer(order, groomer_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

        # 4. Guardar en PostgreSQL (upsert por order_id)
        location = GroomerLocation(
            order_id=order_id,
            groomer_id=groomer_id,
            lat=lat,
            lng=lng,
            accuracy_m=accuracy_m,
            recorded_at=datetime.now(timezone.utc),
        )
        await self.location_store.upsert(location)

        return location
