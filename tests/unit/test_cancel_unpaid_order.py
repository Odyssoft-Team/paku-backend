"""El cliente cancela su reserva sin pagar (p. ej. su tarjeta pidió 3DS) para poder pedir de nuevo."""
import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.app.use_cases_impl import transitions
from app.modules.orders.app.use_cases_impl.transitions import CancelUnpaidOrder
from app.modules.orders.domain.order import Order, OrderStatus, PaymentStatus


class _Repo:
    def __init__(self, order):
        self.order = order

    async def get_order(self, *, id, user_id):
        if id != self.order.id or user_id != self.order.user_id:
            raise ValueError("order_not_found")
        return self.order


@pytest.fixture
def cancelled(monkeypatch):
    calls = []

    async def fake_execute(self, *, order_id):
        calls.append(order_id)
        return replace(self.repo.order, status=OrderStatus.cancelled)

    monkeypatch.setattr(transitions.CancelOrder, "execute", fake_execute)
    return calls


def _order(**kw):
    o = Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=60, currency="PEN")
    return replace(o, **kw)


def _cancel(order, user_id=None):
    return asyncio.run(CancelUnpaidOrder(repo=_Repo(order)).execute(order_id=order.id, user_id=user_id or order.user_id))


def test_unpaid_or_failed_service_order_is_cancelled(cancelled):
    pending = _order()
    assert _cancel(pending).status == OrderStatus.cancelled
    failed = _order(payment_status=PaymentStatus.failed)
    assert _cancel(failed).status == OrderStatus.cancelled
    assert cancelled == [pending.id, failed.id]


@pytest.mark.parametrize("changes, code", [
    ({"payment_status": PaymentStatus.paid}, "ORDER_NOT_CANCELLABLE"),
    ({"payment_status": PaymentStatus.verifying}, "ORDER_NOT_CANCELLABLE"),
    ({"status": OrderStatus.on_the_way}, "ORDER_NOT_CANCELLABLE"),
    ({"status": OrderStatus.done}, "ORDER_NOT_CANCELLABLE"),
    ({"parent_order_id": uuid4()}, "ADJUSTMENT_NOT_CANCELLABLE"),
])
def test_paid_started_or_adjustment_orders_are_not_cancelled(cancelled, changes, code):
    with pytest.raises(HTTPException) as exc:
        _cancel(_order(**changes))
    assert exc.value.status_code == 409 and exc.value.detail["code"] == code
    assert cancelled == []


def test_someone_elses_order_is_404(cancelled):
    with pytest.raises(HTTPException) as exc:
        _cancel(_order(), user_id=uuid4())
    assert exc.value.status_code == 404
