from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.orders.domain.order import Order, OrderStatus


class PostgresOrderRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def _ensure_ready(self) -> None:
        from app.modules.orders.infra.models import ensure_orders_schema

        await ensure_orders_schema(self._engine)

    async def create_order(self, order: Order) -> Order:
        from app.modules.orders.infra.models import OrderModel, utcnow

        await self._ensure_ready()

        model = OrderModel(
            id=order.id,
            user_id=order.user_id,
            status=order.status.value,
            items_snapshot=order.items_snapshot,
            total_snapshot=Decimal(str(order.total_snapshot)),
            currency=order.currency,
            delivery_address_snapshot=order.delivery_address_snapshot,
            created_at=order.created_at,
            updated_at=utcnow(),
        )
        self._session.add(model)
        await self._session.commit()
        return order

    async def create_order_in_tx(self, order: Order) -> Order:
        from app.modules.orders.infra.models import OrderModel, utcnow

        await self._ensure_ready()

        model = OrderModel(
            id=order.id,
            user_id=order.user_id,
            status=order.status.value,
            items_snapshot=order.items_snapshot,
            total_snapshot=Decimal(str(order.total_snapshot)),
            currency=order.currency,
            delivery_address_snapshot=order.delivery_address_snapshot,
            created_at=order.created_at,
            updated_at=utcnow(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return order

    async def get_order(self, *, id: UUID, user_id: UUID) -> Order:
        from app.modules.orders.infra.models import OrderModel

        await self._ensure_ready()

        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")

        return Order(
            id=model.id,
            user_id=model.user_id,
            status=OrderStatus(model.status),
            items_snapshot=model.items_snapshot,
            total_snapshot=float(model.total_snapshot),
            currency=model.currency,
            delivery_address_snapshot=model.delivery_address_snapshot,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_orders(self, *, user_id: UUID) -> list[Order]:
        from app.modules.orders.infra.models import OrderModel

        await self._ensure_ready()

        stmt = select(OrderModel).where(OrderModel.user_id == user_id).order_by(desc(OrderModel.created_at))
        res = await self._session.execute(stmt)
        rows = res.scalars().all()
        return [
            Order(
                id=r.id,
                user_id=r.user_id,
                status=OrderStatus(r.status),
                items_snapshot=r.items_snapshot,
                total_snapshot=float(r.total_snapshot),
                currency=r.currency,
                delivery_address_snapshot=r.delivery_address_snapshot,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def update_status(self, *, id: UUID, status: OrderStatus) -> Order:
        from app.modules.orders.infra.models import OrderModel, utcnow

        await self._ensure_ready()

        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")

        current = OrderStatus(model.status)
        current_order = Order(
            id=model.id,
            user_id=model.user_id,
            status=current,
            items_snapshot=model.items_snapshot,
            total_snapshot=float(model.total_snapshot),
            currency=model.currency,
            delivery_address_snapshot=model.delivery_address_snapshot,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

        if not current_order.can_advance_to(status):
            raise ValueError("invalid_status_transition")

        model.status = status.value
        model.updated_at = utcnow()
        await self._session.commit()

        return await self.get_order(id=id, user_id=model.user_id)

    async def get_order_admin(self, *, id: UUID) -> Optional[Order]:
        from app.modules.orders.infra.models import OrderModel

        await self._ensure_ready()

        model = await self._session.get(OrderModel, id)
        if model is None:
            return None

        return Order(
            id=model.id,
            user_id=model.user_id,
            status=OrderStatus(model.status),
            items_snapshot=model.items_snapshot,
            total_snapshot=float(model.total_snapshot),
            currency=model.currency,
            delivery_address_snapshot=model.delivery_address_snapshot,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
