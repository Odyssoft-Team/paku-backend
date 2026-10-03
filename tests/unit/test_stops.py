"""Pedido 4 (saltar parada y reprogramar) y pedido 5 (avisos de demora)."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.app.use_cases_impl.admin_orders import AssignOrder
from app.modules.orders.app.use_cases_impl.stops import ListDelayReports, ReportDelay, SkipStop
from app.modules.orders.domain.order import Order, OrderStatus, SkipReason

GROOMER = uuid4()


class _OrdersRepo:
    _session = None

    def __init__(self, order):
        self.order = order

    async def get_order_admin(self, *, id):
        return self.order if self.order.id == id else None

    async def mark_skipped(self, *, id, reason, note, at):
        self.order = replace(self.order, status=OrderStatus.skipped, skip_reason=reason, skip_note=note, skipped_at=at)
        return self.order

    async def set_status(self, *, id, status):
        self.order = replace(self.order, status=status)
        return self.order

    async def set_service_step(self, *, id, step, at):
        self.order = replace(self.order, service_step=step,
                             service_steps_log=None if step is None else self.order.service_steps_log,
                             addons_done=None if step is None else self.order.addons_done)
        return self.order

    async def set_groomer(self, *, id, groomer_id, scheduled_at):
        self.order = replace(self.order, groomer_id=groomer_id, scheduled_at=scheduled_at)
        return self.order


class _Users:
    async def list_by_role(self, *, role=None):
        return [SimpleNamespace(id=uuid4())]


class _Delays:
    def __init__(self):
        self.items = []

    async def add(self, report):
        self.items.append(report)
        return report

    async def list_by_order(self, order_id):
        return list(self.items)


class _Assignments:
    async def create(self, assignment):
        return assignment


def _order(status, step=None):
    order = Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=80.0)
    return replace(order, status=status, groomer_id=GROOMER, service_step=step)


def _skip(order, actor=GROOMER):
    repo = _OrdersRepo(order)
    return asyncio.run(SkipStop(repo, _Users()).execute(
        order_id=order.id, reason=SkipReason.pet_not_present, note="no abrió", actor_id=actor, actor_role="groomer",
    ))


@pytest.mark.parametrize("status,step", [(OrderStatus.on_the_way, None), (OrderStatus.in_service, "reception")])
def test_skip_allowed_on_the_way_or_at_reception(status, step):
    out = _skip(_order(status, step))
    assert out.status == OrderStatus.skipped
    assert out.skip_reason == SkipReason.pet_not_present


@pytest.mark.parametrize("status,step", [(OrderStatus.created, None), (OrderStatus.in_service, "bath")])
def test_skip_rejected_elsewhere(status, step):
    with pytest.raises(HTTPException) as err:
        _skip(_order(status, step))
    assert err.value.status_code == 409


def test_skip_by_other_groomer_is_forbidden():
    with pytest.raises(HTTPException) as err:
        _skip(_order(OrderStatus.on_the_way), actor=uuid4())
    assert err.value.status_code == 403


def test_reassigning_skipped_order_returns_it_to_created():
    order = replace(_order(OrderStatus.skipped, "reception"), skip_reason=SkipReason.other)
    repo = _OrdersRepo(order)
    new_groomer = uuid4()

    out, _ = asyncio.run(AssignOrder(repo, _Assignments()).execute(
        order_id=order.id, groomer_id=new_groomer, scheduled_at=datetime(2026, 10, 12, 15, tzinfo=timezone.utc),
        assigned_by=uuid4(),
    ))

    assert out.status == OrderStatus.created
    assert out.service_step is None
    assert out.groomer_id == new_groomer
    assert out.skip_reason == SkipReason.other  # se conserva como historial


def test_delay_report_before_arriving_only():
    order = _order(OrderStatus.on_the_way)
    delays = _Delays()
    use_case = ReportDelay(_OrdersRepo(order), delays, _Users())

    report = asyncio.run(use_case.execute(order_id=order.id, delay_minutes=15, note="tráfico",
                                          actor_id=GROOMER, actor_role="groomer"))
    assert report.delay_minutes == 15

    in_service = _order(OrderStatus.in_service, "bath")
    with pytest.raises(HTTPException) as err:
        asyncio.run(ReportDelay(_OrdersRepo(in_service), delays, _Users()).execute(
            order_id=in_service.id, delay_minutes=15, note=None, actor_id=GROOMER, actor_role="groomer",
        ))
    assert err.value.status_code == 409


def test_delay_reports_visible_to_owner_groomer_admin():
    order = _order(OrderStatus.on_the_way)
    use_case = ListDelayReports(_OrdersRepo(order), _Delays())
    for actor, role in [(order.user_id, "user"), (GROOMER, "groomer"), (uuid4(), "admin")]:
        assert asyncio.run(use_case.execute(order_id=order.id, actor_id=actor, actor_role=role)) == []
    with pytest.raises(HTTPException) as err:
        asyncio.run(use_case.execute(order_id=order.id, actor_id=uuid4(), actor_role="user"))
    assert err.value.status_code == 403
