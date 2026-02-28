from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.booking.domain.hold import AvailabilitySlot


class PostgresAvailabilityRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    def _row_to_slot(self, r) -> AvailabilitySlot:
        return AvailabilitySlot(
            id=r.id,
            service_id=r.service_id,
            date=r.date,
            capacity=r.capacity,
            booked=r.booked,
            is_active=r.is_active,
        )

    async def create_slot(
        self,
        *,
        service_id: UUID,
        date: date_type,
        capacity: int,
        is_active: bool = True,
    ) -> AvailabilitySlot:
        from app.modules.booking.infra.models import AvailabilitySlotModel, utcnow

        now = utcnow()
        model = AvailabilitySlotModel(
            service_id=service_id,
            date=date,
            capacity=capacity,
            booked=0,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_slot(model)

    async def get_slot(self, slot_id: UUID) -> Optional[AvailabilitySlot]:
        from app.modules.booking.infra.models import AvailabilitySlotModel

        model = await self._session.get(AvailabilitySlotModel, slot_id)
        return self._row_to_slot(model) if model else None

    async def get_slot_for_date(
        self, service_id: UUID, date: date_type
    ) -> Optional[AvailabilitySlot]:
        from app.modules.booking.infra.models import AvailabilitySlotModel

        stmt = select(AvailabilitySlotModel).where(
            AvailabilitySlotModel.service_id == service_id,
            AvailabilitySlotModel.date == date,
        )
        res = await self._session.execute(stmt)
        model = res.scalars().first()
        return self._row_to_slot(model) if model else None

    async def get_slot_for_update(
        self, service_id: UUID, date: date_type
    ) -> Optional[AvailabilitySlot]:
        """SELECT FOR UPDATE — use inside a transaction before incrementing booked."""
        from app.modules.booking.infra.models import AvailabilitySlotModel

        stmt = (
            select(AvailabilitySlotModel)
            .where(
                AvailabilitySlotModel.service_id == service_id,
                AvailabilitySlotModel.date == date,
            )
            .with_for_update()
        )
        res = await self._session.execute(stmt)
        model = res.scalars().first()
        return self._row_to_slot(model) if model else None

    async def increment_booked(self, slot_id: UUID) -> None:
        from app.modules.booking.infra.models import AvailabilitySlotModel, utcnow

        stmt = (
            update(AvailabilitySlotModel)
            .where(AvailabilitySlotModel.id == slot_id)
            .values(
                booked=AvailabilitySlotModel.booked + 1,
                updated_at=utcnow(),
            )
        )
        await self._session.execute(stmt)

    async def decrement_booked(self, slot_id: UUID) -> None:
        from app.modules.booking.infra.models import AvailabilitySlotModel, utcnow

        stmt = (
            update(AvailabilitySlotModel)
            .where(
                AvailabilitySlotModel.id == slot_id,
                AvailabilitySlotModel.booked > 0,
            )
            .values(
                booked=AvailabilitySlotModel.booked - 1,
                updated_at=utcnow(),
            )
        )
        await self._session.execute(stmt)

    async def update_slot(self, slot_id: UUID, patch: dict) -> AvailabilitySlot:
        from app.modules.booking.infra.models import AvailabilitySlotModel, utcnow

        model = await self._session.get(AvailabilitySlotModel, slot_id)
        if model is None:
            raise ValueError("slot_not_found")

        allowed = {"capacity"}
        for key, value in patch.items():
            if key in allowed:
                setattr(model, key, value)
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_slot(model)

    async def toggle_slot(self, slot_id: UUID, is_active: bool) -> AvailabilitySlot:
        from app.modules.booking.infra.models import AvailabilitySlotModel, utcnow

        model = await self._session.get(AvailabilitySlotModel, slot_id)
        if model is None:
            raise ValueError("slot_not_found")
        model.is_active = is_active
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_slot(model)

    async def list_slots(
        self,
        *,
        service_id: Optional[UUID] = None,
        date_from: Optional[date_type] = None,
        days: int = 30,
        active_only: bool = False,
    ) -> List[AvailabilitySlot]:
        from app.modules.booking.infra.models import AvailabilitySlotModel

        stmt = select(AvailabilitySlotModel).order_by(
            AvailabilitySlotModel.date.asc()
        )
        if service_id is not None:
            stmt = stmt.where(AvailabilitySlotModel.service_id == service_id)
        if date_from is not None:
            date_to = date_from + timedelta(days=days)
            stmt = stmt.where(
                AvailabilitySlotModel.date >= date_from,
                AvailabilitySlotModel.date < date_to,
            )
        if active_only:
            stmt = stmt.where(AvailabilitySlotModel.is_active.is_(True))

        res = await self._session.execute(stmt)
        return [self._row_to_slot(r) for r in res.scalars().all()]
