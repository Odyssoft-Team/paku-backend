"""Cargo extra por peso: solo un admin lo genera, por el monto guardado en la orden y una sola vez."""
import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.app.use_cases_impl import adjustment as adjustment_module
from app.modules.orders.app.use_cases_impl.adjustment import CreateAdjustmentOrder
from app.modules.orders.domain.order import Order


class _FakeOrdersRepo:
    def __init__(self, order: Order | None):
        self.order = order
        self.created: list[Order] = []
        self.order_pets: list = []

    async def get_order_admin(self, *, id):
        return self.order

    async def create_order(self, order):
        self.created.append(order)
        return order

    async def set_adjustment_order(self, *, id, adjustment_order_id):
        self.order = replace(self.order, adjustment_order_id=adjustment_order_id)
        return self.order

    async def add_order_pets(self, *, order_id, pet_ids):
        self.order_pets.append((order_id, pet_ids))


@pytest.fixture(autouse=True)
def _notifications(monkeypatch):
    sent = []

    async def _notify(_repo, **kwargs):
        sent.append(kwargs)

    monkeypatch.setattr(adjustment_module, "notify_user", _notify)
    return sent


def _order(**fields) -> Order:
    pet_id = uuid4()
    base = {"kind": "service_base", "ref_id": str(uuid4()), "name": "Baño", "qty": 1, "unit_price": 90.0,
            "meta": {"pet_id": str(pet_id), "pet_weight_kg": 15.0}}
    return replace(Order.new(user_id=uuid4(), items_snapshot=[base], total_snapshot=90.0), **fields)


def _run(repo, *, role="admin", order_id=None):
    return asyncio.run(CreateAdjustmentOrder(orders_repo=repo).execute(
        order_id=order_id or (repo.order.id if repo.order else uuid4()), actor_role=role,
    ))


def test_groomer_cannot_create_adjustment():
    repo = _FakeOrdersRepo(_order(extra_charge=5.0, groomer_id=uuid4()))

    with pytest.raises(HTTPException) as err:
        _run(repo, role="groomer")

    assert err.value.status_code == 403
    assert repo.created == []


def test_missing_order_returns_404():
    with pytest.raises(HTTPException) as err:
        _run(_FakeOrdersRepo(None))

    assert err.value.status_code == 404


def test_without_extra_charge_returns_409():
    repo = _FakeOrdersRepo(_order(extra_charge=None))

    with pytest.raises(HTTPException) as err:
        _run(repo)

    assert err.value.status_code == 409
    assert err.value.detail["code"] == "NO_EXTRA_CHARGE"


def test_admin_creates_adjustment_for_stored_amount(_notifications):
    repo = _FakeOrdersRepo(_order(extra_charge=5.0, measured_weight_kg=17.0))

    adjustment = _run(repo)

    assert adjustment.parent_order_id == repo.order.id
    assert adjustment.total_snapshot == 5.0
    assert adjustment.user_id == repo.order.user_id
    assert adjustment.items_snapshot[0]["kind"] == "price_adjustment"
    assert repo.order.adjustment_order_id == adjustment.id
    assert len(repo.order_pets) == 1
    assert _notifications[0]["user_id"] == repo.order.user_id
    assert _notifications[0]["type"] == "pending_balance"


def test_second_adjustment_is_rejected():
    repo = _FakeOrdersRepo(_order(extra_charge=5.0))
    _run(repo)

    with pytest.raises(HTTPException) as err:
        _run(repo)

    assert err.value.status_code == 409
    assert err.value.detail["code"] == "ADJUSTMENT_EXISTS"
    assert len(repo.created) == 1
