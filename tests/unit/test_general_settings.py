"""Feature 0010: parámetros generales (validación, todo o nada) y anticipación mínima para reservar.
SQLite en memoria para el repositorio."""
import asyncio
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.timezone import today_lima
from app.modules.booking.app.use_cases_impl.availability import CreateHold, ListAvailability
from app.modules.booking.domain.hold import AvailabilitySlot
from app.modules.general_settings.app.use_cases import GetSettings, UpdateSettings, booking_min_days_ahead
from app.modules.general_settings.domain.settings import SettingInvalid, resolve, validate_value
from app.modules.general_settings.infra.models import GeneralSettingModel
from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository

ADMIN = uuid4()


def _run(coro):
    return asyncio.run(coro)


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[GeneralSettingModel.__table__])
    return SimpleNamespace(engine=engine, session=async_sessionmaker(engine, expire_on_commit=False)())


async def _close(ctx):
    await ctx.session.close()
    await ctx.engine.dispose()


def test_defaults_and_read_only_values():
    values = resolve({})
    assert values["company_name"] == "Paku"
    assert values["igv_percent"] == 18
    assert values["booking_min_days_ahead"] == 0
    assert (values["timezone"], values["currency"], values["reservation_ttl_minutes"]) == ("America/Lima", "PEN", 120)
    # Lo guardado para un parámetro de solo lectura no se usa
    assert resolve({"currency": "USD"})["currency"] == "PEN"


@pytest.mark.parametrize("key,value", [
    ("company_ruc", "2012345678"),
    ("company_ruc", "20A23456789"),
    ("contact_email", "hola@paku"),
    ("business_hours_open", "8:00"),
    ("business_hours_open", "24:00"),
    ("igv_percent", 120),
    ("igv_percent", "18"),
    ("booking_min_days_ahead", 1.5),
    ("booking_min_days_ahead", True),
    ("currency", "USD"),
    ("timezone", "UTC"),
    ("no_existe", 1),
])
def test_invalid_values(key, value):
    with pytest.raises(SettingInvalid) as exc:
        validate_value(key, value)
    assert exc.value.key == key


def test_valid_values_are_normalized():
    assert validate_value("company_ruc", " 20123456789 ") == "20123456789"
    assert validate_value("contact_phone", "+51 987 654 321") == "+51 987 654 321"
    assert validate_value("igv_percent", 18) == 18.0
    assert validate_value("booking_min_days_ahead", 2.0) == 2
    assert validate_value("company_name", "  ") is None  # vacío = vuelve al valor por defecto


def test_update_is_all_or_nothing_and_null_restores_default():
    async def scenario():
        ctx = await _session()
        repo = PostgresSettingsRepository(session=ctx.session)
        update = UpdateSettings(repo=repo)

        values = await update.execute({"company_name": "Paku Spa", "booking_min_days_ahead": 1}, actor_id=ADMIN)
        assert (values["company_name"], values["booking_min_days_ahead"]) == ("Paku Spa", 1)
        assert await booking_min_days_ahead(ctx.session) == 1

        with pytest.raises(HTTPException) as exc:
            await update.execute({"company_name": "Otro", "company_ruc": "123"}, actor_id=ADMIN)
        assert exc.value.detail["key"] == "company_ruc"
        assert (await GetSettings(repo=repo).execute())["company_name"] == "Paku Spa"  # no guardó nada

        await update.execute({"company_name": None}, actor_id=ADMIN)
        assert (await GetSettings(repo=repo).execute())["company_name"] == "Paku"
        updated_at, updated_by = await repo.last_update()
        assert updated_by == ADMIN and updated_at is not None
        await _close(ctx)
    _run(scenario())


def test_business_hours_must_be_ordered():
    async def scenario():
        ctx = await _session()
        update = UpdateSettings(repo=PostgresSettingsRepository(session=ctx.session))
        await update.execute({"business_hours_open": "08:00", "business_hours_close": "18:00"}, actor_id=ADMIN)
        with pytest.raises(HTTPException) as exc:
            await update.execute({"business_hours_close": "07:30"}, actor_id=ADMIN)
        assert exc.value.detail["key"] == "business_hours_close"
        await _close(ctx)
    _run(scenario())


# ─── Anticipación mínima en booking ──────────────────────────────────────────

def test_hold_respects_min_days_ahead():
    class _Unreachable:
        def __getattr__(self, name):
            raise AssertionError("no debería llegar al repositorio")

    hold = CreateHold(hold_repo=_Unreachable(), availability_repo=_Unreachable(), min_days_ahead=2)
    with pytest.raises(HTTPException) as exc:
        _run(hold.execute(user_id=uuid4(), pet_id=uuid4(), service_id=uuid4(), date=today_lima() + timedelta(days=1)))
    assert exc.value.detail["code"] == "DATE_TOO_SOON"
    assert exc.value.detail["earliest_date"] == (today_lima() + timedelta(days=2)).isoformat()


def test_availability_hides_days_too_soon():
    today = today_lima()

    class _Slots:
        async def list_slots(self, **_):
            return [AvailabilitySlot(id=uuid4(), service_id=uuid4(), date=today + timedelta(days=d), capacity=3,
                                     booked=0, is_active=True) for d in range(4)]

    listing = ListAvailability(repo=_Slots())
    assert len(_run(listing.execute())) == 4  # sin anticipación: como antes
    days = [s.date for s in _run(listing.execute(min_days_ahead=2))]
    assert days == [today + timedelta(days=2), today + timedelta(days=3)]
