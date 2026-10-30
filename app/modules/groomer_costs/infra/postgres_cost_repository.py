from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.groomer_costs.domain.costs import CostItem, CostProfile
from app.modules.groomer_costs.infra.models import GroomerCostProfileModel, utcnow


def _to_profile(m: GroomerCostProfileModel) -> CostProfile:
    return CostProfile(
        id=m.id, groomer_id=m.groomer_id, effective_from=m.effective_from, base_salary=float(m.base_salary),
        items=[CostItem(label=i["label"], kind=i["kind"], value=float(i["value"])) for i in (m.items or [])],
        monthly_hours=float(m.monthly_hours), driving_rest_hours=float(m.driving_rest_hours),
        created_at=m.created_at, notes=m.notes, created_by=m.created_by,
    )


class PostgresCostRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def list_profiles(self, *, groomer_id: Optional[UUID] = None) -> list[CostProfile]:
        """Registros de costo, del más reciente al más antiguo."""
        stmt = select(GroomerCostProfileModel).order_by(
            GroomerCostProfileModel.groomer_id, desc(GroomerCostProfileModel.effective_from)
        )
        if groomer_id is not None:
            stmt = stmt.where(GroomerCostProfileModel.groomer_id == groomer_id)
        return [_to_profile(m) for m in (await self._session.execute(stmt)).scalars().all()]

    async def save_profile(
        self,
        *,
        groomer_id: UUID,
        effective_from: date,
        base_salary: float,
        items: list[CostItem],
        monthly_hours: float,
        driving_rest_hours: float,
        notes: Optional[str],
        created_by: UUID,
    ) -> CostProfile:
        """Crea el registro de esa fecha o lo reemplaza si ya existe (corregir un error)."""
        stmt = select(GroomerCostProfileModel).where(
            GroomerCostProfileModel.groomer_id == groomer_id, GroomerCostProfileModel.effective_from == effective_from,
        )
        m = (await self._session.execute(stmt)).scalars().first()
        if m is None:
            m = GroomerCostProfileModel(groomer_id=groomer_id, effective_from=effective_from)
            self._session.add(m)
        m.base_salary = Decimal(str(base_salary))
        m.items = [{"label": i.label.strip(), "kind": i.kind, "value": i.value} for i in items]
        m.monthly_hours = Decimal(str(monthly_hours))
        m.driving_rest_hours = Decimal(str(driving_rest_hours))
        m.notes = (notes or "").strip() or None
        m.created_by = created_by
        m.created_at = utcnow()
        await self._session.commit()
        await self._session.refresh(m)
        return _to_profile(m)

    async def groomers(self) -> list:
        """Usuarios con rol groomer (UserModel), por nombre."""
        from app.modules.iam.infra.models import UserModel

        stmt = select(UserModel).where(UserModel.role == "groomer").order_by(UserModel.first_name, UserModel.last_name)
        return list((await self._session.execute(stmt)).scalars().all())
