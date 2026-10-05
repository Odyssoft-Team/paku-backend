"""C-17: notificaciones al groomer cuando el admin asigna, reprograma, reasigna o cancela su parada."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.orders.app.use_cases_impl import groomer_notifications as gn
from app.modules.orders.app.use_cases_impl.admin_orders import AssignOrder
from app.modules.orders.app.use_cases_impl.transitions import CancelOrder
from app.modules.orders.domain.order import Order, OrderStatus

PET_ID = uuid4()
T1 = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)   # 10:00 en Lima
T2 = datetime(2026, 10, 11, 19, 30, tzinfo=timezone.utc)  # 14:30 en Lima


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def fake_notify(repo, *, user_id, title, body, data, type="order_status"):
        calls.append(SimpleNamespace(user_id=user_id, title=title, body=body, data=data, type=type))

    monkeypatch.setattr(gn, "notify_user", fake_notify)
    return calls


class _Pets:
    async def get_by_id(self, pet_id, include_deleted=False):
        return SimpleNamespace(id=pet_id, name="Firulais") if pet_id == PET_ID else None


class _Orders:
    _session = None  # la notificación al cliente (directa) es best effort y falla sin sesión

    def __init__(self, order):
        self.order = order

    async def get_order_admin(self, *, id):
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


def _order(**overrides):
    items = [{"kind": "service_base", "ref_id": str(uuid4()), "name": "Baño", "meta": {"pet_id": str(PET_ID)}}]
    address = {"district_id": "150104", "address_line": "Av. Siempre Viva 123"}
    order = Order.new(user_id=uuid4(), items_snapshot=items, total_snapshot=60.0, delivery_address_snapshot=address)
    return replace(order, **overrides)


def _assign(order, groomer_id, scheduled_at):
    use_case = AssignOrder(_Orders(order), _Assignments(), pets_repo=_Pets())
    return asyncio.run(use_case.execute(
        order_id=order.id, groomer_id=groomer_id, scheduled_at=scheduled_at, assigned_by=uuid4(),
    ))


def test_new_assignment_notifies_groomer_with_pet_time_and_district(sent):
    groomer = uuid4()
    _assign(_order(), groomer, T1)

    assert len(sent) == 1
    n = sent[0]
    assert n.user_id == groomer and n.type == "order_assigned"
    assert n.title == "Nueva parada asignada"
    assert n.body == "Firulais · 10/10 10:00 · Barranco"
    assert n.data["order_id"] and n.data["scheduled_at"] == T1.isoformat()


def test_same_groomer_new_time_is_a_reschedule(sent):
    groomer = uuid4()
    _assign(_order(groomer_id=groomer, scheduled_at=T1), groomer, T2)

    assert [(n.user_id, n.type) for n in sent] == [(groomer, "order_rescheduled")]
    assert sent[0].body == "Firulais pasa al 11/10 14:30"


def test_reassigning_notifies_new_and_previous_groomer(sent):
    old, new = uuid4(), uuid4()
    _assign(_order(groomer_id=old, scheduled_at=T1), new, T2)

    assert [(n.user_id, n.type) for n in sent] == [(new, "order_assigned"), (old, "order_unassigned")]
    assert sent[1].body == "Firulais · 10/10 10:00 fue asignada a otro groomer"
    assert sent[1].data == {"order_id": sent[0].data["order_id"]}


def test_skipped_order_back_to_same_groomer_is_a_reschedule(sent):
    groomer = uuid4()
    _assign(_order(groomer_id=groomer, scheduled_at=T1, status=OrderStatus.skipped), groomer, T1)

    assert [n.type for n in sent] == ["order_rescheduled"]


def test_reassigning_with_no_change_sends_nothing_to_groomer(sent):
    groomer = uuid4()
    _assign(_order(groomer_id=groomer, scheduled_at=T1), groomer, T1)

    assert sent == []


def test_cancel_notifies_assigned_groomer(sent):
    groomer = uuid4()
    order = _order(groomer_id=groomer, scheduled_at=T1)
    asyncio.run(CancelOrder(_Orders(order), pets_repo=_Pets()).execute(order_id=order.id))

    assert [(n.user_id, n.type) for n in sent] == [(groomer, "order_cancelled")]
    assert sent[0].body == "Firulais · 10/10 10:00 fue cancelada"
    assert sent[0].data["status"] == "cancelled"


def test_cancel_without_groomer_sends_nothing(sent):
    order = _order()
    asyncio.run(CancelOrder(_Orders(order), pets_repo=_Pets()).execute(order_id=order.id))

    assert sent == []
