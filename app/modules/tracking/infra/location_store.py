"""
Almacenamiento en memoria de la última ubicación conocida del groomer por orden.

Diseño deliberado:
  - Sin base de datos. Sin migración. Sin Alembic.
  - El groomer reporta su posición cada pocos segundos, por lo que si el proceso
    se reinicia la posición se recupera en el siguiente ciclo de reporte.
  - Una sola instancia global por proceso (singleton de módulo).
  - Thread-safe para asyncio (un solo event loop, operaciones O(1) sobre dict).

Si en el futuro se necesita persistencia o coordinación entre workers,
este es el único archivo a reemplazar (por Redis, por ejemplo).
"""

from __future__ import annotations

from uuid import UUID

from app.modules.tracking.domain.location import GroomerLocation


class LocationStore:
    """
    Diccionario en memoria: order_id -> GroomerLocation.
    Mantiene siempre la última posición reportada por el groomer.
    """

    def __init__(self) -> None:
        self._data: dict[UUID, GroomerLocation] = {}

    def upsert(self, location: GroomerLocation) -> None:
        """Guarda o sobreescribe la última posición del groomer para esta orden."""
        self._data[location.order_id] = location

    def get(self, order_id: UUID) -> GroomerLocation | None:
        """Devuelve la última posición conocida, o None si aún no hay datos."""
        return self._data.get(order_id)

    def delete(self, order_id: UUID) -> None:
        """Elimina la entrada cuando el servicio termina o se cancela."""
        self._data.pop(order_id, None)


# ---------------------------------------------------------------------------
# Singleton de proceso — importar este objeto, no instanciar LocationStore.
# ---------------------------------------------------------------------------
location_store = LocationStore()
