"""
PostgreSQL-backed location store.

Reemplaza el LocationStore en memoria para que funcione correctamente
en Cloud Run con múltiples instancias.

Diseño:
  - Tabla ally_locations con una sola fila por order_id (upsert).
  - INSERT ... ON CONFLICT (order_id) DO UPDATE → atómico, sin race conditions.
  - La interfaz pública (upsert / get / delete) es idéntica al LocationStore
    original, por lo que ningún use case necesita cambios.

Intervalo de reporte recomendado: cada 10 segundos desde el app del ally.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracking.domain.location import AllyLocation


class PostgresLocationStore:
    """
    Almacena la última posición conocida del ally en PostgreSQL.
    Una fila por orden (upsert). Compatible con múltiples instancias de Cloud Run.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, location: AllyLocation) -> None:
        """Guarda o sobreescribe la última posición del ally para esta orden."""
        await self._session.execute(
            text(
                """
                INSERT INTO ally_locations
                    (order_id, ally_id, lat, lng, accuracy_m, recorded_at)
                VALUES
                    (:order_id, :ally_id, :lat, :lng, :accuracy_m, :recorded_at)
                ON CONFLICT (order_id) DO UPDATE SET
                    ally_id     = EXCLUDED.ally_id,
                    lat         = EXCLUDED.lat,
                    lng         = EXCLUDED.lng,
                    accuracy_m  = EXCLUDED.accuracy_m,
                    recorded_at = EXCLUDED.recorded_at
                """
            ),
            {
                "order_id":   str(location.order_id),
                "ally_id":    str(location.ally_id),
                "lat":        location.lat,
                "lng":        location.lng,
                "accuracy_m": location.accuracy_m,
                "recorded_at": location.recorded_at,
            },
        )
        await self._session.commit()

    async def get(self, order_id: UUID) -> AllyLocation | None:
        """Devuelve la última posición conocida, o None si aún no hay datos."""
        result = await self._session.execute(
            text(
                """
                SELECT order_id, ally_id, lat, lng, accuracy_m, recorded_at
                FROM ally_locations
                WHERE order_id = :order_id
                """
            ),
            {"order_id": str(order_id)},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return AllyLocation(
            order_id=row["order_id"],
            ally_id=row["ally_id"],
            lat=row["lat"],
            lng=row["lng"],
            accuracy_m=row["accuracy_m"],
            recorded_at=row["recorded_at"],
        )

    async def delete(self, order_id: UUID) -> None:
        """Elimina la entrada cuando el servicio termina o se cancela."""
        await self._session.execute(
            text("DELETE FROM ally_locations WHERE order_id = :order_id"),
            {"order_id": str(order_id)},
        )
        await self._session.commit()
