from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.booking.domain.hold import Hold, HoldStatus


class PostgresHoldRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def _ensure_ready(self) -> None:
        from app.modules.booking.infra.models import ensure_booking_schema

        await ensure_booking_schema(self._engine)

    async def _maybe_expire(self, hold: Hold) -> Hold:
        if hold.status in (HoldStatus.cancelled, HoldStatus.confirmed, HoldStatus.expired):
            return hold
        now = datetime.now(timezone.utc)
        expires_at = hold.expires_at
        if expires_at.tzinfo is None:  # se guarda en UTC; algunos drivers la devuelven sin zona
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            await self.update_status(hold.id, HoldStatus.expired)
            refreshed = await self.get_hold(hold.id)
            return refreshed or hold
        return hold

    async def create_hold(
        self,
        *,
        user_id: UUID,
        pet_id: UUID,
        service_id: UUID,
        expires_at: datetime,
        date=None,
        quote_snapshot: Optional[dict] = None,
    ) -> Hold:
        from app.modules.booking.infra.models import HoldModel, utcnow

        await self._ensure_ready()

        now = utcnow()
        hold = Hold.new(
            user_id=user_id,
            pet_id=pet_id,
            service_id=service_id,
            expires_at=expires_at,
            created_at=now,
            date=date,
            quote_snapshot=quote_snapshot,
        )

        model = HoldModel(
            id=hold.id,
            user_id=hold.user_id,
            pet_id=hold.pet_id,
            service_id=hold.service_id,
            status=hold.status.value,
            expires_at=hold.expires_at,
            date=hold.date,
            quote_snapshot=hold.quote_snapshot,
            created_at=hold.created_at,
            updated_at=now,
        )

        self._session.add(model)
        await self._session.commit()
        return hold

    async def get_hold(self, hold_id: UUID) -> Optional[Hold]:
        from app.modules.booking.infra.models import HoldModel

        await self._ensure_ready()

        model = await self._session.get(HoldModel, hold_id)
        if model is None:
            return None

        hold = Hold(
            id=model.id,
            user_id=model.user_id,
            pet_id=model.pet_id,
            service_id=model.service_id,
            status=HoldStatus(model.status),
            expires_at=model.expires_at,
            created_at=model.created_at,
            date=model.date,
            quote_snapshot=model.quote_snapshot,
        )
        return await self._maybe_expire(hold)

    async def _release_slot(self, *, service_id: UUID, date) -> None:
        """Devuelve el cupo que ocupaba una reserva (booked - 1). No hace commit: va en la misma
        transacción que el cambio de estado de la reserva."""
        from app.modules.booking.infra.models import AvailabilitySlotModel, utcnow

        if date is None:
            return  # reservas sin fecha no ocuparon cupo
        stmt = (
            update(AvailabilitySlotModel)
            .where(
                AvailabilitySlotModel.service_id == service_id,
                AvailabilitySlotModel.date == date,
                AvailabilitySlotModel.booked > 0,
            )
            .values(booked=AvailabilitySlotModel.booked - 1, updated_at=utcnow())
        )
        await self._session.execute(stmt)

    async def update_status(
        self,
        hold_id: UUID,
        status: HoldStatus,
        *,
        quote_snapshot: Optional[dict] = None,
    ) -> Optional[Hold]:
        """
        Solo una reserva `held` cambia de estado (a confirmed, cancelled o expired); los demás
        estados son finales. Cancelar o expirar libera el cupo del día en la misma transacción.
        El UPDATE es condicional (status = held) para que dos requests simultáneos no liberen
        el cupo dos veces.
        """
        from app.modules.booking.infra.models import HoldModel, utcnow

        await self._ensure_ready()

        model = await self._session.get(HoldModel, hold_id)
        if model is None:
            return None

        current = HoldStatus(model.status)
        if current != HoldStatus.held or status == HoldStatus.held:
            return await self.get_hold(hold_id)

        values = {"status": status.value, "updated_at": utcnow()}
        if quote_snapshot is not None:
            values["quote_snapshot"] = quote_snapshot
        result = await self._session.execute(
            update(HoldModel)
            .where(HoldModel.id == hold_id, HoldModel.status == HoldStatus.held.value)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1 and status in (HoldStatus.cancelled, HoldStatus.expired):
            await self._release_slot(service_id=model.service_id, date=model.date)

        await self._session.commit()
        await self._session.refresh(model)
        return await self.get_hold(hold_id)

    async def list_by_user(self, user_id: UUID) -> List[Hold]:
        from app.modules.booking.infra.models import HoldModel

        await self._ensure_ready()

        stmt = select(HoldModel).where(HoldModel.user_id == user_id)
        res = await self._session.execute(stmt)
        rows = res.scalars().all()

        out: List[Hold] = []
        for r in rows:
            hold = Hold(
                id=r.id,
                user_id=r.user_id,
                pet_id=r.pet_id,
                service_id=r.service_id,
                status=HoldStatus(r.status),
                expires_at=r.expires_at,
                created_at=r.created_at,
                date=r.date,
                quote_snapshot=r.quote_snapshot,
            )
            out.append(await self._maybe_expire(hold))
        return out

    async def expire_holds(self, *, now: datetime) -> int:
        """Expira las reservas `held` vencidas y libera el cupo de cada una (cronjob de limpieza)."""
        from app.modules.booking.infra.models import HoldModel

        await self._ensure_ready()

        stmt = (
            select(HoldModel)
            .where(HoldModel.status == HoldStatus.held.value, HoldModel.expires_at < now)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        for model in rows:
            model.status = HoldStatus.expired.value
            model.updated_at = now
            await self._release_slot(service_id=model.service_id, date=model.date)
        await self._session.commit()
        return len(rows)
