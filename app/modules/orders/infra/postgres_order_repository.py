from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.orders.domain.order import Order, OrderStatus, PaymentStatus


class PostgresOrderRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def _ensure_ready(self) -> None:
        from app.modules.orders.infra.models import ensure_orders_schema
        await ensure_orders_schema(self._engine)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_order(r) -> Order:
        return Order(
            id=r.id,
            user_id=r.user_id,
            status=OrderStatus(r.status),
            items_snapshot=r.items_snapshot,
            total_snapshot=float(r.total_snapshot),
            currency=r.currency,
            delivery_address_snapshot=r.delivery_address_snapshot,
            created_at=r.created_at,
            updated_at=r.updated_at,
            ally_id=r.ally_id,
            scheduled_at=r.scheduled_at,
            hold_id=r.hold_id,
            payment_status=PaymentStatus(r.payment_status),
            culqi_charge_id=r.culqi_charge_id,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

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
            ally_id=order.ally_id,
            scheduled_at=order.scheduled_at,
            hold_id=order.hold_id,
            payment_status=order.payment_status.value,
            culqi_charge_id=order.culqi_charge_id,
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
            ally_id=order.ally_id,
            scheduled_at=order.scheduled_at,
            hold_id=order.hold_id,
            payment_status=order.payment_status.value,
            culqi_charge_id=order.culqi_charge_id,
            created_at=order.created_at,
            updated_at=utcnow(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return order

    async def update_status(self, *, id: UUID, status: OrderStatus) -> Order:
        """Avanza el estado validando la transición (mantiene compatibilidad con use cases existentes)."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        current_order = self._row_to_order(model)
        if not current_order.can_advance_to(status):
            raise ValueError("invalid_status_transition")
        model.status = status.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def set_status(self, *, id: UUID, status: OrderStatus) -> Order:
        """Setea el estado sin validar transición. La validación la hace el use case."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        model.status = status.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def confirm_payment(
        self,
        *,
        id: UUID,
        user_id: UUID,
        culqi_charge_id: str,
    ) -> Order:
        """
        Marca la orden como pagada guardando el charge_id de Culqi.
        Solo puede aplicarse a órdenes en payment_status=pending.
        El user_id se verifica para que solo el dueño de la orden pueda confirmar.
        """
        from app.modules.orders.infra.models import OrderModel, utcnow
        from app.modules.orders.domain.order import PaymentStatus
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        if model.payment_status != PaymentStatus.pending.value:
            raise ValueError("payment_already_processed")
        model.payment_status = PaymentStatus.paid.value
        model.culqi_charge_id = culqi_charge_id
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def fail_payment(self, *, id: UUID, user_id: UUID) -> Order:
        """
        Marca la orden como pago fallido.
        Permite que el frontend reintente el pago con otro token/tarjeta.
        """
        from app.modules.orders.infra.models import OrderModel, utcnow
        from app.modules.orders.domain.order import PaymentStatus
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        model.payment_status = PaymentStatus.failed.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def reset_payment_to_pending(self, *, id: UUID, user_id: UUID) -> Order:
        """
        Permite reintentar el pago cuando estaba en failed.
        Solo se puede pasar de failed → pending (para un nuevo intento).
        """
        from app.modules.orders.infra.models import OrderModel, utcnow
        from app.modules.orders.domain.order import PaymentStatus
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        if model.payment_status != PaymentStatus.failed.value:
            raise ValueError("payment_not_failed")
        model.payment_status = PaymentStatus.pending.value
        model.culqi_charge_id = None
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def set_ally(self, *, id: UUID, ally_id: UUID, scheduled_at: datetime) -> Order:
        """Asigna un ally y fecha/hora programada a la orden (lo hace el admin)."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        model.ally_id = ally_id
        model.scheduled_at = scheduled_at
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    # ------------------------------------------------------------------
    # Read — usuario
    # ------------------------------------------------------------------

    async def get_order(self, *, id: UUID, user_id: UUID) -> Order:
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        return self._row_to_order(model)

    async def list_orders(self, *, user_id: UUID) -> list[Order]:
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        stmt = (
            select(OrderModel)
            .where(OrderModel.user_id == user_id)
            .order_by(desc(OrderModel.created_at))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_order(r) for r in rows]

    # ------------------------------------------------------------------
    # Read — admin
    # ------------------------------------------------------------------

    async def get_order_admin(self, *, id: UUID) -> Optional[Order]:
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            return None
        return self._row_to_order(model)

    async def list_orders_admin(
        self,
        *,
        status: Optional[OrderStatus] = None,
        ally_id: Optional[UUID] = None,
    ) -> list[Order]:
        """Lista órdenes con filtros opcionales para el panel de administración."""
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        stmt = select(OrderModel).order_by(desc(OrderModel.created_at))
        if status is not None:
            stmt = stmt.where(OrderModel.status == status.value)
        if ally_id is not None:
            stmt = stmt.where(OrderModel.ally_id == ally_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_order(r) for r in rows]

    # ------------------------------------------------------------------
    # Read — ally
    # ------------------------------------------------------------------

    async def list_orders_by_ally(
        self,
        *,
        ally_id: UUID,
        status: Optional[OrderStatus] = None,
    ) -> list[Order]:
        """Lista las órdenes asignadas a un ally específico."""
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        stmt = (
            select(OrderModel)
            .where(OrderModel.ally_id == ally_id)
            .order_by(OrderModel.scheduled_at.asc().nulls_last())
        )
        if status is not None:
            stmt = stmt.where(OrderModel.status == status.value)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_order(r) for r in rows]
