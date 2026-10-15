"""Feature 0007 — cupo diario compartido por categoría (SQLite en memoria, como test_booking_capacity_release)."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.timezone import today_lima
from app.modules.booking.app.use_cases_impl.availability import CancelHold, CreateHold
from app.modules.booking.infra.models import AvailabilitySlotModel, HoldModel
from app.modules.booking.infra.postgres_availability_repository import PostgresAvailabilityRepository
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
from app.modules.store.infra.db_models import CategoryModel, ProductModel

DAY = today_lima() + timedelta(days=7)


async def _setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[CategoryModel.__table__, ProductModel.__table__, AvailabilitySlotModel.__table__,
                    HoldModel.__table__],
        )
    session = async_sessionmaker(engine, expire_on_commit=False)()
    cat = uuid4()
    session.add(CategoryModel(id=cat, name="PAKU Spa", slug="spa", is_active=True))
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ids = [uuid4(), uuid4(), uuid4()]
    for i, pid in enumerate(ids):  # el primero (más antiguo) es el ancla del cupo
        session.add(ProductModel(id=pid, category_id=cat, name=f"S{i}", species="dog", is_active=True,
                                 created_at=t0 + timedelta(days=i), updated_at=t0))
    await session.commit()
    holds = PostgresHoldRepository(session=session, engine=engine)
    slots = PostgresAvailabilityRepository(session=session, engine=engine)
    return engine, holds, slots, ids


def test_services_of_a_category_share_the_daily_capacity():
    async def scenario():
        engine, holds, slots, (a, b, c) = await _setup()
        # El admin crea el día desde cualquier servicio: queda en el ancla
        slot = await slots.create_slot(service_id=c, date=DAY, capacity=2)
        assert slot.service_id == a

        create = CreateHold(hold_repo=holds, availability_repo=slots)
        h1 = await create.execute(user_id=uuid4(), pet_id=uuid4(), service_id=b, date=DAY)
        await create.execute(user_id=uuid4(), pet_id=uuid4(), service_id=c, date=DAY)
        assert (await slots.get_slot_for_date(a, DAY)).booked == 2
        with pytest.raises(HTTPException):  # sin cupos para ningún servicio de la categoría
            await create.execute(user_id=uuid4(), pet_id=uuid4(), service_id=a, date=DAY)

        # Las reservas del día del cupo incluyen todos los servicios; cancelar libera el cupo común
        assert len(await holds.list_by_slot(service_id=a, date=DAY)) == 2
        await CancelHold(hold_repo=holds, availability_repo=slots).execute(hold_id=h1.id, requester_id=h1.user_id, requester_role="user")
        assert (await slots.get_slot_for_date(c, DAY)).booked == 1
        assert [s.service_id for s in await slots.list_slots(date_from=DAY, days=1)] == [a]
        await engine.dispose()

    asyncio.run(scenario())


def test_open_days_without_service_weekdays_and_bulk_update():
    from app.modules.booking.app.use_cases_impl.availability import (
        CreateAvailabilitySlotsBulk,
        UpdateAvailabilitySlotsBulk,
    )

    async def scenario():
        engine, holds, slots, (a, b, _c) = await _setup()
        monday = DAY - timedelta(days=DAY.weekday()) + timedelta(days=7)
        # Abrir una semana sin servicio, solo lunes a sábado (0..5)
        created, _ = await CreateAvailabilitySlotsBulk(repo=slots).execute(
            service_id=None, date_from=monday, date_to=monday + timedelta(days=6), capacity=10,
            weekdays=[0, 1, 2, 3, 4, 5],
        )
        assert len(created) == 6 and {s.service_id for s in created} == {a}
        assert await slots.get_slot_for_date(b, monday + timedelta(days=6)) is None  # domingo cerrado

        await CreateHold(hold_repo=holds, availability_repo=slots).execute(
            user_id=uuid4(), pet_id=uuid4(), service_id=b, date=monday)
        # Bajar a 1 cupo: el lunes ya tiene 1 reserva, así que se puede; luego cerrar solo los sábados
        updated, below = await UpdateAvailabilitySlotsBulk(repo=slots).execute(
            service_id=None, date_from=monday, date_to=monday + timedelta(days=6), capacity=1)
        assert len(updated) == 6 and below == []
        with pytest.raises(HTTPException):  # nada que cambiar
            await UpdateAvailabilitySlotsBulk(repo=slots).execute(
                service_id=None, date_from=monday, date_to=monday)
        updated, _ = await UpdateAvailabilitySlotsBulk(repo=slots).execute(
            service_id=None, date_from=monday, date_to=monday + timedelta(days=6), weekdays=[5], is_active=False)
        assert [s.date.weekday() for s in updated] == [5] and updated[0].is_active is False
        await engine.dispose()

    asyncio.run(scenario())
