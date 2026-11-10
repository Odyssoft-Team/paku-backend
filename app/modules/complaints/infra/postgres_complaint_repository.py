from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.complaints.domain.complaints import format_code
from app.modules.complaints.infra.models import ComplaintCounterModel, ComplaintModel


class PostgresComplaintRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def add_with_next_number(self, complaint: ComplaintModel, *, year: int) -> ComplaintModel:
        """Asigna el siguiente correlativo del año y guarda la hoja en la misma transacción.

        La fila del contador queda bloqueada (FOR UPDATE) hasta el commit, así dos envíos simultáneos no reciben
        el mismo número; la restricción única (year, number) es la última defensa.
        """
        stmt = select(ComplaintCounterModel).where(ComplaintCounterModel.year == year).with_for_update()
        counter = (await self._session.execute(stmt)).scalar_one_or_none()
        if counter is None:
            counter = ComplaintCounterModel(year=year, last_number=0)
            self._session.add(counter)
        counter.last_number += 1
        complaint.year = year
        complaint.number = counter.last_number
        complaint.code = format_code(year, counter.last_number)
        self._session.add(complaint)
        await self._session.commit()
        return complaint

    async def get(self, complaint_id: UUID) -> Optional[ComplaintModel]:
        return await self._session.get(ComplaintModel, complaint_id)

    async def list(self, *, status: Optional[str], limit: int, offset: int) -> tuple[list[ComplaintModel], int]:
        base = select(ComplaintModel)
        if status:
            base = base.where(ComplaintModel.status == status)
        total = (await self._session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self._session.execute(
            base.order_by(ComplaintModel.created_at.desc()).limit(limit).offset(offset)
        )).scalars().all()
        return list(rows), int(total)

    async def save(self, complaint: ComplaintModel) -> ComplaintModel:
        await self._session.commit()
        return complaint
