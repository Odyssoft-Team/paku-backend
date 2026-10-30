"""Lecturas para el dashboard gerencial (feature 0014). Solo lee tablas de otros módulos; no escribe nada."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.booking.infra.models import AvailabilitySlotModel
from app.modules.dashboard.domain.dashboard import SlotDay
from app.modules.orders.domain.order import (
    REQUESTED_SERVICE_PAYMENT_STATUSES,
    REQUESTED_SERVICE_STATUSES,
    OrderStatus,
)
from app.modules.orders.infra.models import OrderDelayReportModel, OrderModel
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository

_PAID_OR_VERIFYING = [s.value for s in REQUESTED_SERVICE_PAYMENT_STATUSES]


class PostgresDashboardReadRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def _orders(self, stmt) -> list:
        rows = (await self._session.execute(stmt)).scalars().all()
        return [PostgresOrderRepository._row_to_order(r) for r in rows]

    async def cancelled_orders(self, start: datetime, end: datetime) -> list:
        """Órdenes de servicio canceladas (pagadas o en verificación) actualizadas en [start, end)."""
        return await self._orders(select(OrderModel).where(
            OrderModel.parent_order_id.is_(None),
            OrderModel.status == OrderStatus.cancelled.value,
            OrderModel.payment_status.in_(_PAID_OR_VERIFYING),
            OrderModel.updated_at >= start,
            OrderModel.updated_at < end,
        ))

    async def requested_orders(self) -> list:
        """Servicios solicitados (feature 0003): pagados o en verificación, sin terminar ni cancelar."""
        return await self._orders(select(OrderModel).where(
            OrderModel.parent_order_id.is_(None),
            OrderModel.status.in_([s.value for s in REQUESTED_SERVICE_STATUSES]),
            OrderModel.payment_status.in_(_PAID_OR_VERIFYING),
        ))

    async def slots(self, date_from: date, date_to: date) -> list[SlotDay]:
        """Cupos de los días activos del rango (uno por servicio y día)."""
        stmt = select(AvailabilitySlotModel.date, AvailabilitySlotModel.capacity, AvailabilitySlotModel.booked).where(
            AvailabilitySlotModel.is_active.is_(True),
            AvailabilitySlotModel.date >= date_from,
            AvailabilitySlotModel.date <= date_to,
        )
        return [SlotDay(day=d, capacity=c, booked=b) for d, c, b in (await self._session.execute(stmt)).all()]

    async def delay_report_times(self, start: datetime, end: datetime) -> list[datetime]:
        stmt = select(OrderDelayReportModel.created_at).where(
            OrderDelayReportModel.created_at >= start, OrderDelayReportModel.created_at < end,
        )
        return list((await self._session.execute(stmt)).scalars().all())
