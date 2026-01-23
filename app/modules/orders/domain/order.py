from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class OrderStatus(str, Enum):
    created = "created"
    in_process = "in_process"
    on_the_way = "on_the_way"
    delivered = "delivered"


_STATUS_ORDER: dict[OrderStatus, int] = {
    OrderStatus.created: 1,
    OrderStatus.in_process: 2,
    OrderStatus.on_the_way: 3,
    OrderStatus.delivered: 4,
}


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

    def can_advance_to(self, new_status: OrderStatus) -> bool:
        return _STATUS_ORDER[new_status] >= _STATUS_ORDER[self.status]
