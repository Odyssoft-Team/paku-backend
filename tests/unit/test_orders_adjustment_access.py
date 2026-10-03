"""Cargo extra por peso: solo el groomer asignado a la orden o un admin pueden crearlo."""
import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.app.use_cases_impl.adjustment import CreateAdjustmentOrder
from app.modules.orders.domain.order import Order


class _FakeOrdersRepo:
    def __init__(self, order: Order | None):
        self.order = order

    async def get_order_admin(self, *, id):
        return self.order


class _FakePetsRepo:
    def __init__(self):
        self.calls = 0

    async def get_by_id(self, pet_id):
        self.calls += 1
        return None  # corta el flujo con 404 una vez superada la autorización


def _use_case(order):
    pets = _FakePetsRepo()
    return CreateAdjustmentOrder(orders_repo=_FakeOrdersRepo(order), pets_repo=pets, store_repo=None), pets


def test_unassigned_groomer_gets_403_before_touching_the_pet():
    order = replace(Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=80.0), groomer_id=uuid4())
    use_case, pets = _use_case(order)

    with pytest.raises(HTTPException) as err:
        asyncio.run(use_case.execute(order_id=order.id, pet_id=uuid4(), actor_id=uuid4(), actor_role="groomer"))

    assert err.value.status_code == 403
    assert pets.calls == 0


@pytest.mark.parametrize("role", ["groomer", "admin"])
def test_assigned_groomer_and_admin_pass_authorization(role):
    groomer_id = uuid4()
    order = replace(Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=80.0), groomer_id=groomer_id)
    use_case, pets = _use_case(order)
    actor_id = groomer_id if role == "groomer" else uuid4()

    with pytest.raises(HTTPException) as err:
        asyncio.run(use_case.execute(order_id=order.id, pet_id=uuid4(), actor_id=actor_id, actor_role=role))

    # Pasó la autorización y llegó a buscar la mascota (inexistente en el fake → 404).
    assert err.value.status_code == 404
    assert pets.calls == 1


def test_missing_order_returns_404():
    use_case, _ = _use_case(None)

    with pytest.raises(HTTPException) as err:
        asyncio.run(use_case.execute(order_id=uuid4(), pet_id=uuid4(), actor_id=uuid4(), actor_role="admin"))

    assert err.value.status_code == 404
