"""
Almacenamiento en memoria de la última ubicación conocida del ally por orden.

Diseño deliberado:
  - Sin base de datos. Sin migración. Sin Alembic.
  - El ally reporta su posición cada pocos segundos, por lo que si el proceso
    se reinicia la posición se recupera en el siguiente ciclo de reporte.
  - Una sola instancia global por proceso (singleton de módulo).
  - Thread-safe para asyncio (un solo event loop, operaciones O(1) sobre dict).

Si en el futuro se necesita persistencia o coordinación entre workers,
este es el único archivo a reemplazar (por Redis, por ejemplo).
"""

from __future__ import annotations

from uuid import UUID

from app.modules.tracking.domain.location import AllyLocation


class LocationStore:
    """
    Diccionario en memoria: order_id -> AllyLocation.
    Mantiene siempre la última posición reportada por el ally.
    """

    def __init__(self) -> None:
        self._data: dict[UUID, AllyLocation] = {}

    def upsert(self, location: AllyLocation) -> None:
        """Guarda o sobreescribe la última posición del ally para esta orden."""
        self._data[location.order_id] = location

    def get(self, order_id: UUID) -> AllyLocation | None:
        """Devuelve la última posición conocida, o None si aún no hay datos."""
        return self._data.get(order_id)

    def delete(self, order_id: UUID) -> None:
        """Elimina la entrada cuando el servicio termina o se cancela."""
        self._data.pop(order_id, None)


# ---------------------------------------------------------------------------
# Singleton de proceso — importar este objeto, no instanciar LocationStore.
# ---------------------------------------------------------------------------
location_store = LocationStore()
