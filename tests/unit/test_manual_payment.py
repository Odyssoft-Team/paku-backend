"""C-63: un admin registra un cobro hecho fuera de la app (efectivo, transferencia u otro)."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.app.use_cases_impl.payment import RegisterManualPayment
from app.modules.orders.domain.order import Order, OrderStatus, PaymentMethod, PaymentStatus

ADMIN = uuid4()


class _Repo:
    def __init__(self, order):
        self.order = order
        self.calls = []

    async def get_order_admin(self, *, id):
        return self.order if id == self.order.id else None

    async def register_manual_payment(self, *, id, method, note, actor_id):
        self.calls.append((method, note, actor_id))
        self.order = replace(self.order, payment_status=PaymentStatus.paid, payment_method=method, payment_note=note,
                             payment_registered_by=actor_id, payment_registered_at=datetime.now(timezone.utc))
        return self.order


def _order(**kw):
    return replace(Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=85, currency="PEN"), **kw)


def _register(repo, order_id=None, method="transfer", note="Op. 123456 BCP"):
    return asyncio.run(RegisterManualPayment(orders_repo=repo).execute(
        order_id=order_id or repo.order.id, method=method, note=note, actor_id=ADMIN))


@pytest.mark.parametrize("payment", [PaymentStatus.pending, PaymentStatus.failed])
def test_pending_or_failed_order_becomes_paid_with_note(payment):
    repo = _Repo(_order(status=OrderStatus.done, payment_status=payment))
    order = _register(repo, note="  Op. 123456 BCP  ")
    assert order.payment_status == PaymentStatus.paid and order.payment_method == PaymentMethod.transfer
    assert repo.calls == [(PaymentMethod.transfer, "Op. 123456 BCP", ADMIN)]


@pytest.mark.parametrize("method", ["cash", "other", "card", "yape"])
def test_manual_methods_include_culqi_outside_the_app(method):
    assert _register(_Repo(_order()), method=method).payment_method == PaymentMethod(method)


@pytest.mark.parametrize("changes, code", [
    ({"payment_status": PaymentStatus.paid}, "PAYMENT_NOT_PENDING"),
    ({"payment_status": PaymentStatus.verifying}, "PAYMENT_NOT_PENDING"),
    ({"status": OrderStatus.cancelled}, "ORDER_CANCELLED"),
])
def test_paid_verifying_or_cancelled_orders_are_rejected(changes, code):
    repo = _Repo(_order(**changes))
    with pytest.raises(HTTPException) as exc:
        _register(repo)
    assert exc.value.status_code == 409 and exc.value.detail["code"] == code and repo.calls == []


@pytest.mark.parametrize("method, note, code", [
    ("bitcoin", "Op. 1", "PAYMENT_METHOD_INVALID"),
    ("cash", "  ", "PAYMENT_NOTE_REQUIRED"),
])
def test_invalid_method_or_missing_note(method, note, code):
    repo = _Repo(_order())
    with pytest.raises(HTTPException) as exc:
        _register(repo, method=method, note=note)
    assert exc.value.status_code == 422 and exc.value.detail["code"] == code


def test_a_manual_payment_can_be_corrected_but_not_an_app_payment():
    repo = _Repo(_order(status=OrderStatus.done))
    _register(repo, method="transfer", note="Por error")
    fixed = _register(repo, method="card", note="Link de pago Culqi chr_123")
    assert (fixed.payment_method, fixed.payment_note) == (PaymentMethod.card, "Link de pago Culqi chr_123")

    paid_in_app = _Repo(_order(payment_status=PaymentStatus.paid, payment_method=PaymentMethod.card))
    with pytest.raises(HTTPException) as exc:
        _register(paid_in_app)
    assert exc.value.detail["code"] == "PAYMENT_NOT_PENDING"


def test_unknown_order_is_404():
    with pytest.raises(HTTPException) as exc:
        _register(_Repo(_order()), order_id=uuid4())
    assert exc.value.status_code == 404
