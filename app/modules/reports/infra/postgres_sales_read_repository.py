"""Lecturas para el reporte de ventas (feature 0016). Solo lee tablas de otros módulos; no escribe nada."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.campaigns.infra.models import CampaignModel
from app.modules.iam.infra.models import UserModel
from app.modules.orders.domain.order import PaymentStatus
from app.modules.orders.infra.models import OrderModel
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.pets.infra.models import PetModel


class PostgresSalesReadRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def service_orders(self, *, created_from: Optional[datetime] = None,
                             created_to: Optional[datetime] = None) -> list:
        """Órdenes de servicio (sin orden padre), opcionalmente creadas en [created_from, created_to)."""
        stmt = select(OrderModel).where(OrderModel.parent_order_id.is_(None))
        if created_from is not None:
            stmt = stmt.where(OrderModel.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(OrderModel.created_at < created_to)
        rows = (await self._session.execute(stmt.order_by(OrderModel.created_at))).scalars().all()
        return [PostgresOrderRepository._row_to_order(r) for r in rows]

    async def paid_extras(self, parent_ids: list[UUID]) -> dict[UUID, float]:
        """Suma de los cargos extra pagados (órdenes de ajuste) de cada orden."""
        if not parent_ids:
            return {}
        stmt = select(OrderModel.parent_order_id, OrderModel.total_snapshot).where(
            OrderModel.parent_order_id.in_(parent_ids), OrderModel.payment_status == PaymentStatus.paid.value,
        )
        out: dict[UUID, float] = {}
        for parent, total in (await self._session.execute(stmt)).all():
            out[parent] = out.get(parent, 0.0) + float(total)
        return out

    async def users(self, ids: list[UUID]) -> dict[UUID, UserModel]:
        if not ids:
            return {}
        rows = (await self._session.execute(select(UserModel).where(UserModel.id.in_(ids)))).scalars().all()
        return {r.id: r for r in rows}

    async def pet_names(self, ids: list[UUID]) -> dict[UUID, str]:
        if not ids:
            return {}
        stmt = select(PetModel.id, PetModel.name).where(PetModel.id.in_(ids))  # también las borradas
        return {pid: name for pid, name in (await self._session.execute(stmt)).all()}

    async def campaign_names(self, ids: list[UUID]) -> dict[UUID, str]:
        if not ids:
            return {}
        stmt = select(CampaignModel.id, CampaignModel.name).where(CampaignModel.id.in_(ids))
        return {cid: name for cid, name in (await self._session.execute(stmt)).all()}
