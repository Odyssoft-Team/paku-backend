"""Reglas de reserva (2026-10-04): la reserva vence con el carrito, se confirma con la orden y se libera
si la orden se cancela o se salta. SQLite en memoria solo para la lógica del repositorio."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.timezone import today_lima
from app.modules.booking.app.use_cases_impl.availability import (
    CreateAvailabilitySlot,
    CreateHold,
    ListSlotHolds,
    UpdateAvailabilitySlot,
)
from app.modules.booking.domain.hold import HoldStatus
from app.modules.booking.infra.models import AvailabilitySlotModel, HoldModel
from app.modules.booking.infra.postgres_availability_repository import PostgresAvailabilityRepository
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
from app.modules.cart.app.use_cases_impl.hold_binding import CartHolds
from app.modules.cart.domain.cart import CartItemKind
from app.modules.orders.app.use_cases import _confirm_cart_hold
from app.modules.orders.app.use_cases_impl.transitions import CancelOrder
from app.modules.orders.domain.order import Order, OrderStatus
from app.modules.store.infra.db_models import CategoryModel, ProductModel

DAY = today_lima() + timedelta(days=7)


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
    slot_id = uuid4()
    session.add(AvailabilitySlotModel(id=slot_id, service_id=service_id, date=DAY, capacity=capacity, booked=0,
                                      is_active=True))
    await session.commit()
    ctx = SimpleNamespace(
        engine=engine, session=session, service_id=service_id, slot_id=slot_id,
        holds=PostgresHoldRepository(session=session, engine=engine),
        slots=PostgresAvailabilityRepository(session=session, engine=engine),
    )
    return ctx


async def _close(ctx):
    await ctx.session.close()
    await ctx.engine.dispose()


async def _booked(ctx) -> int:
    return (await ctx.slots.get_slot_for_date(ctx.service_id, DAY)).booked


async def _hold(ctx, *, user_id=None, pet_id=None, date=DAY):
    return await CreateHold(hold_repo=ctx.holds, availability_repo=ctx.slots).execute(
        user_id=user_id or uuid4(), pet_id=pet_id or uuid4(), service_id=ctx.service_id, date=date,
    )


def _run(fn):
    asyncio.run(fn())


# --- reservar -------------------------------------------------------------

def test_hold_lasts_as_long_as_the_cart():
    async def scenario():
        ctx = await _setup()
        hold = await _hold(ctx)
        remaining = hold.expires_at - datetime.now(timezone.utc)
        assert timedelta(hours=1, minutes=59) < remaining <= timedelta(hours=2)
        await _close(ctx)
    _run(scenario)


def test_past_date_is_rejected():
    async def scenario():
        ctx = await _setup()
        with pytest.raises(HTTPException) as err:
            await _hold(ctx, date=today_lima() - timedelta(days=1))
        assert err.value.detail["code"] == "DATE_IN_PAST"
        await _close(ctx)
    _run(scenario)


def test_one_active_hold_per_pet_and_day():
    async def scenario():
        ctx = await _setup(capacity=5)
        pet_id = uuid4()
        await _hold(ctx, pet_id=pet_id)
        with pytest.raises(HTTPException) as err:
            await _hold(ctx, pet_id=pet_id)
        assert err.value.status_code == 409
        assert err.value.detail["code"] == "HOLD_ALREADY_EXISTS"
        assert await _booked(ctx) == 1
        await _close(ctx)
    _run(scenario)


def test_pet_of_another_user_is_rejected():
    async def scenario():
        ctx = await _setup()

        class _Pets:
            async def get_by_id(self, pet_id):
                return SimpleNamespace(id=pet_id, owner_id=uuid4())

        with pytest.raises(HTTPException) as err:
            await CreateHold(hold_repo=ctx.holds, availability_repo=ctx.slots, pets_repo=_Pets()).execute(
                user_id=uuid4(), pet_id=uuid4(), service_id=ctx.service_id, date=DAY,
            )
        assert err.value.status_code == 403
        await _close(ctx)
    _run(scenario)


# --- admin ----------------------------------------------------------------

def test_capacity_cannot_go_below_booked():
    async def scenario():
        ctx = await _setup(capacity=3)
        await _hold(ctx)
        await _hold(ctx)
        with pytest.raises(HTTPException) as err:
            await UpdateAvailabilitySlot(ctx.slots).execute(ctx.slot_id, capacity=1)
        assert err.value.detail["code"] == "CAPACITY_BELOW_BOOKED"
        out = await UpdateAvailabilitySlot(ctx.slots).execute(ctx.slot_id, capacity=2)
        assert out.capacity == 2
        await _close(ctx)
    _run(scenario)


def test_duplicate_slot_returns_409_not_500():
    async def scenario():
        ctx = await _setup()
        with pytest.raises(HTTPException) as err:
            await CreateAvailabilitySlot(ctx.slots).execute(service_id=ctx.service_id, date=DAY, capacity=3)
        assert err.value.status_code == 409
        assert err.value.detail["code"] == "SLOT_EXISTS"
        await _close(ctx)
    _run(scenario)


def test_admin_sees_who_booked_the_day():
    async def scenario():
        ctx = await _setup()
        a = await _hold(ctx)
        b = await _hold(ctx)
        holds = await ListSlotHolds(ctx.holds, ctx.slots).execute(slot_id=ctx.slot_id)
        assert {h.id for h in holds} == {a.id, b.id}
        await _close(ctx)
    _run(scenario)


# --- carrito → orden → cancelación ------------------------------------------

def _base_line(hold, **meta):
    return {"kind": CartItemKind.service_base.value, "ref_id": str(hold.service_id),
            "meta": {"pet_id": str(hold.pet_id), "hold_id": str(hold.id), "scheduled_time": "10:00", **meta}}


def test_cart_binding_fills_date_and_aligns_expiry():
    async def scenario():
        ctx = await _setup()
        hold = await _hold(ctx)
        cart_holds = CartHolds(ctx.holds)

        lines = await cart_holds.bind([_base_line(hold)], user_id=hold.user_id)
        assert lines[0]["meta"]["scheduled_date"] == DAY.isoformat()

        cart_expires = datetime.now(timezone.utc) + timedelta(minutes=90)
        await cart_holds.attach(hold.id, cart_expires_at=cart_expires)
        refreshed = await ctx.holds.get_hold(hold.id)
        assert abs((refreshed.expires_at.replace(tzinfo=timezone.utc) - cart_expires).total_seconds()) < 1
        await _close(ctx)
    _run(scenario)


@pytest.mark.parametrize("problem", ["missing", "other_user", "date", "expired"])
def test_cart_binding_rejects_bad_holds(problem):
    async def scenario():
        ctx = await _setup()
        hold = await _hold(ctx)
        line, user_id = _base_line(hold), hold.user_id
        expected = {"missing": "HOLD_REQUIRED", "other_user": "HOLD_NOT_OWNED",
                    "date": "HOLD_MISMATCH", "expired": "HOLD_EXPIRED"}[problem]
        if problem == "missing":
            line["meta"].pop("hold_id")
        elif problem == "other_user":
            user_id = uuid4()
        elif problem == "date":
            line["meta"]["scheduled_date"] = (DAY + timedelta(days=1)).isoformat()
        else:
            await ctx.holds.expire_holds(now=datetime.now(timezone.utc) + timedelta(hours=3))

        with pytest.raises(HTTPException) as err:
            await CartHolds(ctx.holds).bind([line], user_id=user_id)
        assert err.value.detail["code"] == expected
        await _close(ctx)
    _run(scenario)


def test_order_confirms_hold_and_cancel_releases_it():
    async def scenario():
        ctx = await _setup()
        hold = await _hold(ctx)
        assert await _booked(ctx) == 1

        # Crear la orden confirma la reserva: ya no vence aunque pase el tiempo del carrito.
        hold_id = await _confirm_cart_hold(ctx.holds, [_base_line(hold)], user_id=hold.user_id)
        assert hold_id == hold.id
        assert await ctx.holds.expire_holds(now=datetime.now(timezone.utc) + timedelta(hours=5)) == 0
        assert (await ctx.holds.get_hold(hold.id)).status == HoldStatus.confirmed
        assert await _booked(ctx) == 1

        # Cancelar la orden libera el cupo.
        order = replace(Order.new(user_id=hold.user_id, items_snapshot=[], total_snapshot=50.0), hold_id=hold.id)

        class _Orders:
            _session = None

            async def get_order_admin(self, *, id):
                return order

            async def set_status(self, *, id, status):
                return replace(order, status=status)

        out = await CancelOrder(_Orders(), holds_repo=ctx.holds).execute(order_id=order.id)
        assert out.status == OrderStatus.cancelled
        assert (await ctx.holds.get_hold(hold.id)).status == HoldStatus.cancelled
        assert await _booked(ctx) == 0
        await _close(ctx)
    _run(scenario)


def test_order_with_expired_hold_returns_hold_expired():
    async def scenario():
        ctx = await _setup()
        hold = await _hold(ctx)
        await ctx.holds.expire_holds(now=datetime.now(timezone.utc) + timedelta(hours=3))
        with pytest.raises(HTTPException) as err:
            await _confirm_cart_hold(ctx.holds, [_base_line(hold)], user_id=hold.user_id)
        assert err.value.detail["code"] == "HOLD_EXPIRED"
        await _close(ctx)
    _run(scenario)
