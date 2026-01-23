from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
from uuid import UUID

from app.modules.orders.domain.order import Order, OrderStatus


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._by_id: Dict[UUID, Order] = {}
        self._by_user: Dict[UUID, List[UUID]] = {}

    def create_order(self, order: Order) -> Order:
        self._by_id[order.id] = order
        if order.user_id not in self._by_user:
            self._by_user[order.user_id] = []
        self._by_user[order.user_id].append(order.id)
        return order

    def get_order(self, id: UUID, user_id: UUID) -> Order:
        order = self._by_id.get(id)
        if not order or order.user_id != user_id:
            raise ValueError("order_not_found")
        return order

    def list_orders(self, user_id: UUID) -> list[Order]:
        ids = self._by_user.get(user_id, [])
        out: List[Order] = []
        for order_id in ids:
            order = self._by_id.get(order_id)
            if order is None:
                continue
            out.append(order)
        return out

    def update_status(self, id: UUID, status: OrderStatus) -> Order:
        order = self._by_id.get(id)
        if not order:
            raise ValueError("order_not_found")

        if not order.can_advance_to(status):
            raise ValueError("invalid_status_transition")

        updated = Order(
            id=order.id,
            user_id=order.user_id,
            status=status,
            items_snapshot=order.items_snapshot,
            total_snapshot=order.total_snapshot,
            currency=order.currency,
            delivery_address_snapshot=order.delivery_address_snapshot,
            created_at=order.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._by_id[id] = updated
        return updated
