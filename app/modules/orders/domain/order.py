from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


# [TECH]
# Enum defining order lifecycle states with ordinal mapping.
#
# [NATURAL/BUSINESS]
# Estados por los que pasa un pedido hasta entregarse.
class OrderStatus(str, Enum):
    created = "created"
    in_process = "in_process"
    on_the_way = "on_the_way"
    delivered = "delivered"


# [TECH]
# Ordinal mapping for status transition validation.
#
# [NATURAL/BUSINESS]
# Define el orden correcto de los estados del pedido.
_STATUS_ORDER: dict[OrderStatus, int] = {
    OrderStatus.created: 1,
    OrderStatus.in_process: 2,
    OrderStatus.on_the_way: 3,
    OrderStatus.delivered: 4,
}


# [TECH]
# Immutable entity with immutable snapshots and status flow.
#
# [NATURAL/BUSINESS]
# Pedido con productos, total y dirección de entrega.
@dataclass(frozen=True)
class Order:
    id: UUID
    user_id: UUID
    status: OrderStatus
    items_snapshot: Any
    total_snapshot: float
    currency: str
    delivery_address_snapshot: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    # [TECH]
    # Factory creating Order with created status and timestamps.
    #
    # [NATURAL/BUSINESS]
    # Crea un pedido nuevo con estado inicial creado.
    @staticmethod
    def new(
        *,
        user_id: UUID,
        items_snapshot: Any,
        total_snapshot: float,
        currency: str = "PEN",
        delivery_address_snapshot: Optional[dict[str, Any]] = None,
    ) -> "Order":
        now = datetime.now(timezone.utc)
        return Order(
            id=uuid4(),
            user_id=user_id,
            status=OrderStatus.created,
            items_snapshot=items_snapshot,
            total_snapshot=total_snapshot,
            currency=currency,
            delivery_address_snapshot=delivery_address_snapshot,
            created_at=now,
            updated_at=now,
        )

    # [TECH]
    # Validates forward-only status transitions using ordinals.
    #
    # [NATURAL/BUSINESS]
    # Verifica si el pedido puede pasar al siguiente estado.
    def can_advance_to(self, new_status: OrderStatus) -> bool:
        return _STATUS_ORDER[new_status] >= _STATUS_ORDER[self.status]
