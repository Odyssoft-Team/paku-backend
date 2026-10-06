"""C-20 (aviso a admins de pedido pagado), C-21 (el cupo sigue al día asignado, reserved_date,
scheduled_time opcional) y alerta Android de los push."""
import asyncio
import sys
import types
from collections import namedtuple
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.timezone import LIMA_TZ, today_lima
from app.modules.booking.app.use_cases_impl.availability import CreateHold
from app.modules.booking.domain.hold import HoldStatus
from app.modules.booking.infra.models import AvailabilitySlotModel, HoldModel
from app.modules.booking.infra.postgres_availability_repository import PostgresAvailabilityRepository
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
from app.modules.cart.app.use_cases_impl.validation import _validate_required_meta_fields
from app.modules.orders.api.schemas import OrderOut
from app.modules.orders.app.use_cases_impl import admin_notifications, stops
from app.modules.orders.app.use_cases_impl.admin_orders import AssignOrder
from app.modules.orders.domain.order import Order
from app.modules.push.domain.push import PushMessage
from app.modules.store.infra.db_models import CategoryModel, ProductModel

DAY1 = today_lima() + timedelta(days=5)
DAY2 = DAY1 + timedelta(days=1)


def _at(day, hour=10):
    """datetime en UTC que corresponde a `hour` de ese día en Lima."""
    return datetime.combine(day, time(hour), tzinfo=LIMA_TZ).astimezone(timezone.utc)


# --- C-21: mover el cupo al asignar -----------------------------------------

class _Orders:
    """Repo de órdenes en memoria (las reservas y cupos van por SQLite)."""
    _session = None

    def __init__(self, order):
        self.order = order

    async def get_order_admin(self, *, id):
        return self.order

    async def set_reservation(self, *, id, hold_id, reserved_date):
        self.order = replace(self.order, hold_id=hold_id or self.order.hold_id, reserved_date=reserved_date)
        return self.order

    async def set_status(self, *, id, status):
        self.order = replace(self.order, status=status)
        return self.order

    async def set_service_step(self, *, id, step, at):
        self.order = replace(self.order, service_step=step)
        return self.order

    async def set_groomer(self, *, id, groomer_id, scheduled_at):
        self.order = replace(self.order, groomer_id=groomer_id, scheduled_at=scheduled_at)
        return self.order


class _Assignments:
    async def create(self, assignment):
        return assignment


async def _setup(capacity_day2=2):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[
            CategoryModel.__table__, ProductModel.__table__, AvailabilitySlotModel.__table__, HoldModel.__table__,
        ])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    service_id = uuid4()
    for day, cap in ((DAY1, 2), (DAY2, capacity_day2)):
        session.add(AvailabilitySlotModel(id=uuid4(), service_id=service_id, date=day, capacity=cap, booked=0,
                                          is_active=True))
    await session.commit()
    holds = PostgresHoldRepository(session=session, engine=engine)
    slots = PostgresAvailabilityRepository(session=session, engine=engine)

    # Orden con reserva vigente (confirmada) en DAY1
    user_id, pet_id = uuid4(), uuid4()
    hold = await CreateHold(hold_repo=holds, availability_repo=slots).execute(
        user_id=user_id, pet_id=pet_id, service_id=service_id, date=DAY1,
    )
    hold = await holds.update_status(hold.id, HoldStatus.confirmed)
    items = [{"kind": "service_base", "ref_id": str(service_id), "name": "Baño", "meta": {"pet_id": str(pet_id)}}]
    order = Order.new(user_id=user_id, items_snapshot=items, total_snapshot=60.0, hold_id=hold.id, reserved_date=DAY1)
    return SimpleNamespace(engine=engine, session=session, holds=holds, slots=slots, hold=hold,
                           orders=_Orders(order), service_id=service_id)


async def _booked(ctx, day):
    return (await ctx.slots.get_slot_for_date(ctx.service_id, day)).booked


async def _assign(ctx, when):
    use_case = AssignOrder(ctx.orders, _Assignments(), holds_repo=ctx.holds, availability_repo=ctx.slots)
    return await use_case.execute(order_id=ctx.orders.order.id, groomer_id=uuid4(), scheduled_at=when,
                                  assigned_by=uuid4())


def test_same_day_keeps_the_slot():
    async def scenario():
        ctx = await _setup()
        order, _ = await _assign(ctx, _at(DAY1, 15))
        assert order.hold_id == ctx.hold.id and order.reserved_date == DAY1
        assert await _booked(ctx, DAY1) == 1 and await _booked(ctx, DAY2) == 0
        await ctx.session.close(); await ctx.engine.dispose()
    asyncio.run(scenario())


def test_other_day_moves_the_slot():
    async def scenario():
        ctx = await _setup()
        order, _ = await _assign(ctx, _at(DAY2))
        assert order.reserved_date == DAY2 and order.hold_id != ctx.hold.id
        assert (await ctx.holds.get_hold(ctx.hold.id)).status == HoldStatus.cancelled
        assert (await ctx.holds.get_hold(order.hold_id)).status == HoldStatus.confirmed
        assert await _booked(ctx, DAY1) == 0 and await _booked(ctx, DAY2) == 1
        await ctx.session.close(); await ctx.engine.dispose()
    asyncio.run(scenario())


def test_full_day_returns_409_and_changes_nothing():
    async def scenario():
        ctx = await _setup(capacity_day2=0)
        with pytest.raises(HTTPException) as err:
            await _assign(ctx, _at(DAY2))
        assert err.value.status_code == 409
        assert err.value.detail["code"] == "NO_CAPACITY"
        assert DAY2.strftime("%d/%m/%Y") in err.value.detail["message"]
        assert ctx.orders.order.reserved_date == DAY1 and ctx.orders.order.groomer_id is None
        assert await _booked(ctx, DAY1) == 1
        await ctx.session.close(); await ctx.engine.dispose()
    asyncio.run(scenario())


def test_without_valid_hold_takes_a_slot_on_the_chosen_day():
    async def scenario():
        ctx = await _setup()
        await ctx.holds.release(ctx.hold.id)  # p. ej. la parada se saltó y el cupo se liberó
        ctx.orders.order = replace(ctx.orders.order, reserved_date=None)
        order, _ = await _assign(ctx, _at(DAY1))  # mismo día que la reserva vieja: igual toma cupo
        assert order.reserved_date == DAY1 and order.hold_id != ctx.hold.id
        assert await _booked(ctx, DAY1) == 1
        await ctx.session.close(); await ctx.engine.dispose()
    asyncio.run(scenario())


# --- C-21: reserved_date y scheduled_time opcional ----------------------------

def test_order_out_exposes_reserved_date():
    order = Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=1.0, reserved_date=DAY1)
    assert OrderOut(**order.__dict__).model_dump(mode="json")["reserved_date"] == DAY1.isoformat()


def test_scheduled_time_is_optional_but_validated_if_sent():
    base = {"kind": "service_base", "ref_id": "x", "meta": {"pet_id": "p", "hold_id": "h"}}
    _validate_required_meta_fields([base])  # sin hora: OK
    with pytest.raises(HTTPException):
        _validate_required_meta_fields([{**base, "meta": {**base["meta"], "scheduled_time": "25:99"}}])


# --- C-20: aviso a los admins --------------------------------------------------

@pytest.fixture
def admin_calls(monkeypatch):
    calls = []

    async def fake_notify(repo, *, user_id, title, body, data, type="order_status"):
        calls.append(SimpleNamespace(user_id=user_id, title=title, body=body, data=data, type=type))

    monkeypatch.setattr(stops, "notify_user", fake_notify)
    return calls


class _Users:
    def __init__(self, admins):
        self.admins = admins

    async def list_by_role(self, *, role=None):
        return [SimpleNamespace(id=a) for a in self.admins]


class _Pets:
    def __init__(self, pet_id):
        self.pet_id = pet_id

    async def get_by_id(self, pet_id, include_deleted=False):
        return SimpleNamespace(id=pet_id, name="Firulais") if pet_id == self.pet_id else None


def _paid_order(**overrides):
    pet_id = uuid4()
    items = [{"kind": "service_base", "ref_id": str(uuid4()), "name": "Baño completo", "meta": {"pet_id": str(pet_id)}}]
    order = Order.new(user_id=uuid4(), items_snapshot=items, total_snapshot=60.0, reserved_date=DAY1,
                      delivery_address_snapshot={"district_id": "150104", "address_line": "Av. X 1"})
    return replace(order, **overrides), pet_id


def test_paid_service_order_notifies_every_admin(admin_calls):
    order, pet_id = _paid_order()
    admins = [uuid4(), uuid4()]
    asyncio.run(admin_notifications.notify_admins_order_paid(
        SimpleNamespace(_session=None), order, users_repo=_Users(admins), pets_repo=_Pets(pet_id),
    ))
    assert [c.user_id for c in admin_calls] == admins
    c = admin_calls[0]
    assert c.type == "order_paid" and c.title == "Nuevo pedido por asignar"
    assert c.body == f"Firulais · Baño completo · {DAY1.strftime('%d/%m')} · Barranco"
    assert c.data == {"order_id": str(order.id), "scheduled_date": DAY1.isoformat()}


def test_adjustment_orders_do_not_notify_admins(admin_calls):
    order, pet_id = _paid_order(parent_order_id=uuid4())
    asyncio.run(admin_notifications.notify_admins_order_paid(
        SimpleNamespace(_session=None), order, users_repo=_Users([uuid4()]), pets_repo=_Pets(pet_id),
    ))
    assert admin_calls == []


# --- Push: alerta Android ------------------------------------------------------

def _fake_expo_sdk(monkeypatch, message_type):
    published = []

    class _Client:
        def publish_multiple(self, messages):
            published.extend(messages)
            return []

    sdk = types.ModuleType("exponent_server_sdk")
    sdk.PushClient = _Client
    sdk.PushMessage = message_type
    for name in ("DeviceNotRegisteredError", "PushServerError", "PushTicketError"):
        setattr(sdk, name, type(name, (Exception,), {}))
    monkeypatch.setitem(sys.modules, "exponent_server_sdk", sdk)
    return published


def test_expo_push_sends_sound_priority_and_channel(monkeypatch):
    from app.modules.push.infra.provider import ExpoPushProvider

    Msg = namedtuple("Msg", "to title body data sound priority channel_id")
    published = _fake_expo_sdk(monkeypatch, Msg)
    ExpoPushProvider().send(["ExponentPushToken[a]"], PushMessage(title="t", body="b", data={}))
    assert published[0].sound == "default" and published[0].priority == "high"
    assert published[0].channel_id == "default"


def test_expo_push_falls_back_if_sdk_lacks_fields(monkeypatch):
    from app.modules.push.infra.provider import ExpoPushProvider

    Msg = namedtuple("Msg", "to title body data")
    published = _fake_expo_sdk(monkeypatch, Msg)
    ExpoPushProvider().send(["ExponentPushToken[a]"], PushMessage(title="t", body="b", data={}))
    assert len(published) == 1  # se envía igual, sin los campos extra
