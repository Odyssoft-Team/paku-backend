"""Liberación de cupo del booking por día.

Usa SQLite en memoria solo para ejercitar la lógica del repositorio sin PostgreSQL
(la app exige PostgreSQL; aquí no se prueban tipos ni locks propios de Postgres).
"""
import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.timezone import today_lima
from app.modules.cart.domain.cart import CART_TTL_HOURS
from app.modules.booking.app.use_cases_impl.availability import CancelHold, CreateHold
from app.modules.booking.domain.hold import HoldStatus
from app.modules.booking.infra.models import AvailabilitySlotModel, HoldModel
from app.modules.booking.infra.postgres_availability_repository import PostgresAvailabilityRepository
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
from app.modules.store.infra.db_models import CategoryModel, ProductModel  # FK de availability_slots

DAY = today_lima() + timedelta(days=7)
AFTER_EXPIRY = timedelta(hours=CART_TTL_HOURS, minutes=1)


async def _setup(capacity: int = 2):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[CategoryModel.__table__, ProductModel.__table__, AvailabilitySlotModel.__table__,
                    HoldModel.__table__],
        )
    session = async_sessionmaker(engine, expire_on_commit=False)()
    service_id = uuid4()
    session.add(AvailabilitySlotModel(id=uuid4(), service_id=service_id, date=DAY, capacity=capacity, booked=0,
                                      is_active=True))
    await session.commit()
    holds = PostgresHoldRepository(session=session, engine=engine)
    slots = PostgresAvailabilityRepository(session=session, engine=engine)
    return engine, session, holds, slots, service_id


async def _booked(slots, service_id) -> int:
    slot = await slots.get_slot_for_date(service_id, DAY)
    return slot.booked


async def _create(holds, slots, service_id, user_id):
    return await CreateHold(hold_repo=holds, availability_repo=slots).execute(
        user_id=user_id, pet_id=uuid4(), service_id=service_id, date=DAY,
    )


def test_cancel_releases_capacity_once():
    async def scenario():
        engine, session, holds, slots, service_id = await _setup()
        user_id = uuid4()
        hold = await _create(holds, slots, service_id, user_id)
        assert await _booked(slots, service_id) == 1

        cancel = CancelHold(hold_repo=holds, availability_repo=slots)
        out = await cancel.execute(hold_id=hold.id, requester_id=user_id, requester_role="user")
        assert out.status == HoldStatus.cancelled
        assert await _booked(slots, service_id) == 0

        # Cancelar de nuevo es idempotente y no libera dos veces.
        await cancel.execute(hold_id=hold.id, requester_id=user_id, requester_role="user")
        assert await _booked(slots, service_id) == 0
        await session.close()
        await engine.dispose()

    asyncio.run(scenario())


def test_cancel_by_another_user_is_forbidden_and_keeps_capacity():
    async def scenario():
        engine, session, holds, slots, service_id = await _setup()
        hold = await _create(holds, slots, service_id, uuid4())

        with pytest.raises(HTTPException) as err:
            await CancelHold(hold_repo=holds, availability_repo=slots).execute(
                hold_id=hold.id, requester_id=uuid4(), requester_role="user",
            )
        assert err.value.status_code == 403
        assert await _booked(slots, service_id) == 1
        await session.close()
        await engine.dispose()

    asyncio.run(scenario())


def test_cleanup_job_expiration_releases_capacity():
    async def scenario():
        engine, session, holds, slots, service_id = await _setup()
        await _create(holds, slots, service_id, uuid4())
        await _create(holds, slots, service_id, uuid4())
        assert await _booked(slots, service_id) == 2

        # La reserva dura lo mismo que el carrito: antes de ese plazo no vence.
        assert await holds.expire_holds(now=datetime.now(timezone.utc) + timedelta(minutes=30)) == 0

        expired = await holds.expire_holds(now=datetime.now(timezone.utc) + AFTER_EXPIRY)
        assert expired == 2
        assert await _booked(slots, service_id) == 0

        # Una segunda corrida no encuentra nada ni descuenta de más.
        assert await holds.expire_holds(now=datetime.now(timezone.utc) + AFTER_EXPIRY) == 0
        assert await _booked(slots, service_id) == 0
        await session.close()
        await engine.dispose()

    asyncio.run(scenario())


def test_confirmed_hold_keeps_capacity():
    async def scenario():
        engine, session, holds, slots, service_id = await _setup()
        hold = await _create(holds, slots, service_id, uuid4())
        await holds.update_status(hold.id, HoldStatus.confirmed)

        assert await holds.expire_holds(now=datetime.now(timezone.utc) + AFTER_EXPIRY) == 0
        assert await _booked(slots, service_id) == 1
        await session.close()
        await engine.dispose()

    asyncio.run(scenario())
