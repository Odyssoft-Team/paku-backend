"""
Dominio del módulo tracking.

Responsabilidades:
  - Definir el value object GroomerLocation.
  - Definir las reglas de negocio puras (sin I/O) que gobiernan el ciclo
    de vida del tracking en función del estado de la orden.

Reglas de negocio:
  - El groomer puede reportar su posición cuando la orden está en on_the_way
    o in_service (ya llegó pero el cliente puede tener el mapa abierto).
  - El cliente, el groomer y el admin pueden leer la posición cuando la orden
    está en on_the_way o in_service.
  - Fuera de esos estados el tracking está cerrado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.orders.domain.order import Order, OrderStatus


# ---------------------------------------------------------------------------
# Estados en los que el tracking está activo
# ---------------------------------------------------------------------------

# Escritura: el groomer puede reportar posición
TRACKING_WRITABLE_STATUSES: frozenset[OrderStatus] = frozenset(
    {OrderStatus.on_the_way, OrderStatus.in_service}
)

# Lectura: el cliente puede consultar la posición
TRACKING_READABLE_STATUSES: frozenset[OrderStatus] = frozenset(
    {OrderStatus.on_the_way, OrderStatus.in_service}
)


# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GroomerLocation:
    """Última posición conocida del groomer para una orden activa."""
    order_id: UUID
    groomer_id: UUID
    lat: float
    lng: float
    accuracy_m: float | None   # precisión GPS en metros, opcional
    recorded_at: datetime      # UTC, momento en que el groomer reportó


# ---------------------------------------------------------------------------
# Reglas puras — sin I/O, lanzan ValueError con código descriptivo
# ---------------------------------------------------------------------------

def assert_tracking_writable(order: Order) -> None:
    """
    Verifica que el tracking acepta escrituras para esta orden.
    El groomer puede reportar posición en on_the_way e in_service.
    """
    if order.status not in TRACKING_WRITABLE_STATUSES:
        raise ValueError(
            f"tracking_not_active: order status is '{order.status.value}', "
            f"expected one of {[s.value for s in TRACKING_WRITABLE_STATUSES]}"
        )


def assert_tracking_readable(order: Order) -> None:
    """
    Verifica que el tracking tiene datos visibles para esta orden.
    """
    if order.status not in TRACKING_READABLE_STATUSES:
        raise ValueError(
            f"tracking_not_available: order status is '{order.status.value}', "
            f"expected one of {[s.value for s in TRACKING_READABLE_STATUSES]}"
        )


def assert_is_groomer(order: Order, groomer_id: UUID) -> None:
    """Verifica que el requester es el groomer asignado a la orden."""
    if order.groomer_id is None:
        raise ValueError("tracking_forbidden: order has no groomer assigned")
    if order.groomer_id != groomer_id:
        raise ValueError("tracking_forbidden: requester is not the assigned groomer")


def assert_can_read(order: Order, requester_id: UUID, requester_role: str) -> None:
    """
    Verifica que el requester tiene permiso de lectura.
    - Cliente dueño de la orden.
    - Groomer asignado a la orden.
    - Admin (cualquier orden).
    """
    is_owner = requester_id == order.user_id
    is_groomer  = requester_id == order.groomer_id
    is_admin = requester_role == "admin"

    if not (is_owner or is_groomer or is_admin):
        raise ValueError(
            "tracking_forbidden: requester is not a participant of this order"
        )
