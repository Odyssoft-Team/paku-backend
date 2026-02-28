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
        if hold.expires_at <= now:
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

    async def update_status(
        self,
        hold_id: UUID,
        status: HoldStatus,
        *,
        quote_snapshot: Optional[dict] = None,
    ) -> Optional[Hold]:
        from app.modules.booking.infra.models import HoldModel, utcnow

        await self._ensure_ready()

        model = await self._session.get(HoldModel, hold_id)
        if model is None:
            return None

        current = HoldStatus(model.status)
        if current == HoldStatus.expired:
            return await self.get_hold(hold_id)
        if current == HoldStatus.held and status not in (HoldStatus.confirmed, HoldStatus.cancelled, HoldStatus.expired):
            return await self.get_hold(hold_id)
        if current in (HoldStatus.confirmed, HoldStatus.cancelled) and status != current:
            return await self.get_hold(hold_id)

        model.status = status.value
        if quote_snapshot is not None:
            model.quote_snapshot = quote_snapshot
        model.updated_at = utcnow()

        await self._session.commit()
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
        from app.modules.booking.infra.models import HoldModel

        await self._ensure_ready()

        stmt = (
            update(HoldModel)
            .where(HoldModel.status == HoldStatus.held.value, HoldModel.expires_at < now)
            .values(status=HoldStatus.expired.value, updated_at=now)
        )
        res = await self._session.execute(stmt)
        await self._session.commit()
        return int(res.rowcount or 0)
