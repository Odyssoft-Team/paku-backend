"""Lecturas para el CRM (feature 0011): clientes, sus mascotas y sus órdenes, en pocas consultas.

Solo lee tablas de otros módulos (`iam`, `pets`, `orders`); no escribe nada.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iam.infra.models import UserAddressModel, UserModel
from app.modules.orders.domain.order import OrderStatus, PaymentStatus
from app.modules.orders.infra.models import OrderModel
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.pets.infra.models import PetModel


class PostgresCustomerReadRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def service_orders(self, *, user_id: Optional[UUID] = None) -> list:
        """Órdenes de servicio terminadas y los cargos extra pagados (órdenes de ajuste)."""
        stmt = select(OrderModel).where(or_(
            and_(OrderModel.parent_order_id.is_(None), OrderModel.status == OrderStatus.done.value),
            and_(OrderModel.parent_order_id.is_not(None), OrderModel.payment_status == PaymentStatus.paid.value),
        ))
        if user_id is not None:
            stmt = stmt.where(OrderModel.user_id == user_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [PostgresOrderRepository._row_to_order(r) for r in rows]

    async def users(self, ids: list[UUID]) -> dict[UUID, UserModel]:
        if not ids:
            return {}
        rows = (await self._session.execute(select(UserModel).where(UserModel.id.in_(ids)))).scalars().all()
        return {r.id: r for r in rows}

    async def default_district_ids(self, user_ids: list[UUID]) -> dict[UUID, str]:
        """Distrito de la dirección principal (vigente) de cada usuario."""
        if not user_ids:
            return {}
        stmt = select(UserAddressModel.user_id, UserAddressModel.district_id).where(
            UserAddressModel.user_id.in_(user_ids),
            UserAddressModel.is_default.is_(True),
            UserAddressModel.deleted_at.is_(None),
        )
        return {uid: did for uid, did in (await self._session.execute(stmt)).all()}

    async def pets_by_owner(self, owner_ids: list[UUID]) -> dict[UUID, list[PetModel]]:
        if not owner_ids:
            return {}
        stmt = select(PetModel).where(PetModel.owner_id.in_(owner_ids), PetModel.deleted_at.is_(None)).order_by(
            PetModel.created_at
        )
        out: dict[UUID, list[PetModel]] = {}
        for pet in (await self._session.execute(stmt)).scalars().all():
            out.setdefault(pet.owner_id, []).append(pet)
        return out
