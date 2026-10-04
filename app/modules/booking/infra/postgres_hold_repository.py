from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.booking.domain.hold import Hold, HoldStatus


def _aware(value: datetime) -> datetime:
    """Las fechas se guardan en UTC; algunos drivers las devuelven sin zona."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class PostgresHoldRepository:
    """
    Reservas de cupo por día.

    Ciclo de vida:
      held       → reservada mientras el cliente compra (vence con el carrito, CART_TTL_HOURS)
      confirmed  → la compra terminó en una orden; ya no vence
      cancelled  → liberada (cliente/admin la canceló, o la orden se canceló/saltó)
      expired    → venció sin comprar (cronjob o lectura)
    Toda salida de held/confirmed hacia cancelled/expired devuelve el cupo del día en la misma
    transacción, con UPDATE condicional para no liberar dos veces.
    """

    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def _ensure_ready(self) -> None:
        from app.modules.booking.infra.models import ensure_booking_schema

        await ensure_booking_schema(self._engine)

    @staticmethod
    def _row_to_hold(model) -> Hold:
        return Hold(
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

    async def _maybe_expire(self, hold: Hold) -> Hold:
        if hold.status != HoldStatus.held:
            return hold
        if _aware(hold.expires_at) <= datetime.now(timezone.utc):
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
        return await self._maybe_expire(self._row_to_hold(model))

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

    async def _transition(
        self, hold_id: UUID, *, from_statuses: tuple[HoldStatus, ...], to: HoldStatus, values: Optional[dict] = None,
    ) -> Optional[Hold]:
        """Cambio de estado condicional; libera el cupo si el destino es cancelled/expired."""
        from app.modules.booking.infra.models import HoldModel, utcnow

        await self._ensure_ready()
        model = await self._session.get(HoldModel, hold_id)
        if model is None:
            return None
        if HoldStatus(model.status) not in from_statuses:
            return await self.get_hold(hold_id)

        result = await self._session.execute(
            update(HoldModel)
            .where(HoldModel.id == hold_id, HoldModel.status.in_([s.value for s in from_statuses]))
            .values(status=to.value, updated_at=utcnow(), **(values or {}))
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1 and to in (HoldStatus.cancelled, HoldStatus.expired):
            await self._release_slot(service_id=model.service_id, date=model.date)

        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_hold(model)

    async def update_status(
        self,
        hold_id: UUID,
        status: HoldStatus,
        *,
        quote_snapshot: Optional[dict] = None,
    ) -> Optional[Hold]:
        """Solo una reserva `held` cambia de estado (a confirmed, cancelled o expired)."""
        if status == HoldStatus.held:
            return await self.get_hold(hold_id)
        values = {"quote_snapshot": quote_snapshot} if quote_snapshot is not None else None
        return await self._transition(hold_id, from_statuses=(HoldStatus.held,), to=status, values=values)

    async def release(self, hold_id: UUID) -> Optional[Hold]:
        """Libera una reserva reservada o confirmada (ej. la orden se canceló o la parada se saltó)."""
        return await self._transition(
            hold_id, from_statuses=(HoldStatus.held, HoldStatus.confirmed), to=HoldStatus.cancelled,
        )

    async def set_expiry(self, hold_id: UUID, expires_at: datetime) -> Optional[Hold]:
        """Alinea el vencimiento de una reserva `held` con el de su carrito."""
        from app.modules.booking.infra.models import HoldModel, utcnow

        await self._ensure_ready()
        await self._session.execute(
            update(HoldModel)
            .where(HoldModel.id == hold_id, HoldModel.status == HoldStatus.held.value)
            .values(expires_at=expires_at, updated_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        await self._session.commit()
        model = await self._session.get(HoldModel, hold_id)
        if model is not None:
            await self._session.refresh(model)
        return self._row_to_hold(model) if model is not None else None

    async def list_by_user(self, user_id: UUID) -> List[Hold]:
        from app.modules.booking.infra.models import HoldModel

        await self._ensure_ready()
        stmt = select(HoldModel).where(HoldModel.user_id == user_id).order_by(HoldModel.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [await self._maybe_expire(self._row_to_hold(r)) for r in rows]

    async def list_by_slot(self, *, service_id: UUID, date) -> List[Hold]:
        """Reservas de un día y servicio (para el admin), más recientes primero."""
        from app.modules.booking.infra.models import HoldModel

        await self._ensure_ready()
        stmt = (
            select(HoldModel)
            .where(HoldModel.service_id == service_id, HoldModel.date == date)
            .order_by(HoldModel.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [await self._maybe_expire(self._row_to_hold(r)) for r in rows]

    async def find_active_for_pet(self, *, pet_id: UUID, date) -> Optional[Hold]:
        """Reserva vigente (held no vencida, o confirmed) de la mascota para ese día."""
        from app.modules.booking.infra.models import HoldModel

        await self._ensure_ready()
        stmt = select(HoldModel).where(
            HoldModel.pet_id == pet_id,
            HoldModel.date == date,
            HoldModel.status.in_([HoldStatus.held.value, HoldStatus.confirmed.value]),
        )
        for row in (await self._session.execute(stmt)).scalars().all():
            hold = await self._maybe_expire(self._row_to_hold(row))
            if hold.status in (HoldStatus.held, HoldStatus.confirmed):
                return hold
        return None

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
