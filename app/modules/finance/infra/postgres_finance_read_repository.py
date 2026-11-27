"""Lecturas del P&L mensual (feature 0024). Solo lectura sobre órdenes, comprobantes, inventario y usuarios."""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class PostgresFinanceReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _all(self, stmt) -> list:
        return list((await self._session.execute(stmt)).scalars().all())

    async def services_done(self, start: datetime, end: datetime) -> list:
        """Órdenes de servicio terminadas cuyo término (o última actualización, si faltara) cae en [start, end)."""
        from app.modules.orders.infra.models import OrderModel as O

        day = func.coalesce(O.completed_at, O.updated_at)
        return await self._all(select(O).where(
            O.status == "done", O.parent_order_id.is_(None), day >= start, day < end,
        ).order_by(day))

    async def adjustments_of(self, parent_ids: Iterable[UUID]) -> list:
        """Ajustes por peso (órdenes hijas) no cancelados de esas órdenes."""
        from app.modules.orders.infra.models import OrderModel as O

        ids = [i for i in set(parent_ids) if i]
        if not ids:
            return []
        return await self._all(select(O).where(O.parent_order_id.in_(ids), O.status != "cancelled"))

    async def cancelled_paid(self, start: datetime, end: datetime) -> list:
        """Órdenes de servicio canceladas y pagadas cuya cancelación (última actualización) cae en [start, end)."""
        from app.modules.orders.infra.models import OrderModel as O

        return await self._all(select(O).where(
            O.status == "cancelled", O.payment_status == "paid", O.parent_order_id.is_(None),
            O.updated_at >= start, O.updated_at < end,
        ).order_by(O.updated_at))

    async def valid_documents(self, order_ids: Iterable[UUID]) -> dict:
        """Comprobante vigente más reciente de cada orden."""
        from app.modules.invoicing.domain.intifact import NO_VIGENTES
        from app.modules.invoicing.infra.models import InvoiceDocumentModel as D

        ids = [i for i in set(order_ids) if i]
        if not ids:
            return {}
        rows = await self._all(select(D).where(D.order_id.in_(ids), D.status.not_in(NO_VIGENTES))
                               .order_by(D.created_at))
        return {d.order_id: d for d in rows}   # el último gana

    async def movements(self, start: date, end: date) -> list[tuple]:
        """Consumos, mermas y ajustes vigentes con fecha en [start, end], con el nombre del insumo."""
        from app.modules.inventory.infra.models import MovementModel as M
        from app.modules.inventory.infra.models import SupplyModel as S

        stmt = (select(M, S.name).join(S, S.id == M.supply_id)
                .where(M.type.in_(("consumption", "waste", "adjustment")), M.voided_at.is_(None),
                       M.occurred_on >= start, M.occurred_on <= end)
                .order_by(M.occurred_on, M.seq))
        return list((await self._session.execute(stmt)).all())

    async def users_by_id(self, ids: Iterable[UUID]) -> dict:
        from app.modules.iam.infra.models import UserModel

        ids = [i for i in set(ids) if i]
        if not ids:
            return {}
        return {u.id: u for u in await self._all(select(UserModel).where(UserModel.id.in_(ids)))}

    async def active_groomers(self) -> list:
        from app.modules.iam.infra.models import UserModel

        return await self._all(select(UserModel).where(UserModel.role == "groomer", UserModel.is_active.is_(True)))

    async def order_pet_names(self, order_ids: Iterable[UUID]) -> dict[UUID, str]:
        from app.modules.orders.infra.models import OrderPetModel
        from app.modules.pets.infra.models import PetModel

        ids = [i for i in set(order_ids) if i]
        if not ids:
            return {}
        rows = (await self._session.execute(
            select(OrderPetModel.order_id, PetModel.name).join(PetModel, PetModel.id == OrderPetModel.pet_id)
            .where(OrderPetModel.order_id.in_(ids)))).all()
        out: dict[UUID, list[str]] = {}
        for order_id, name in rows:
            out.setdefault(order_id, []).append(name)
        return {k: ", ".join(v) for k, v in out.items()}


def full_name(user) -> Optional[str]:
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
