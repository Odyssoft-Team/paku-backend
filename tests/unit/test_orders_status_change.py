"""Cambio de estado genérico de órdenes (POST /orders/{id}/status; PATCH /orders/{id} se eliminó).

Reglas: solo admin (cualquier orden) o el groomer asignado; el cliente no. Los errores deben
salir como 403/404/409 (antes el parámetro `status` tapaba a `fastapi.status` y daba 500).
"""
import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.app.use_cases import UpdateOrderStatus
from app.modules.orders.domain.order import Order, OrderStatus


class _FakeOrdersRepo:
    _session = None  # la notificación es best effort y falla sin sesión

    def __init__(self, order: Order | None):
        self.order = order
        self.updated_to: list[OrderStatus] = []

    async def get_order_admin(self, *, id):
        if self.order is None or self.order.id != id:
            return None
        return self.order

    async def update_status(self, *, id, status):
        self.updated_to.append(status)
        self.order = replace(self.order, status=status)
        return self.order


def _order(**overrides) -> Order:
    base = Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=50.0)
    return replace(base, **overrides)


def _run(coro):
    return asyncio.run(coro)


def test_admin_advances_any_order():
    order = _order()
    repo = _FakeOrdersRepo(order)

    out = _run(UpdateOrderStatus(repo).execute(
        order_id=order.id, status=OrderStatus.on_the_way, actor_id=uuid4(), actor_role="admin",
    ))

    assert out.status == OrderStatus.on_the_way
    assert repo.updated_to == [OrderStatus.on_the_way]


def test_assigned_groomer_advances_own_order():
    groomer_id = uuid4()
    order = _order(groomer_id=groomer_id)
    repo = _FakeOrdersRepo(order)

    out = _run(UpdateOrderStatus(repo).execute(
        order_id=order.id, status=OrderStatus.on_the_way, actor_id=groomer_id, actor_role="groomer",
    ))

    assert out.status == OrderStatus.on_the_way


def test_other_groomer_gets_403():
    order = _order(groomer_id=uuid4())
    repo = _FakeOrdersRepo(order)

    with pytest.raises(HTTPException) as err:
        _run(UpdateOrderStatus(repo).execute(
            order_id=order.id, status=OrderStatus.on_the_way, actor_id=uuid4(), actor_role="groomer",
        ))

    assert err.value.status_code == 403
    assert repo.updated_to == []


def test_client_owner_cannot_change_status():
    order = _order()
    repo = _FakeOrdersRepo(order)

    with pytest.raises(HTTPException) as err:
        _run(UpdateOrderStatus(repo).execute(
            order_id=order.id, status=OrderStatus.done, actor_id=order.user_id, actor_role="user",
        ))

    assert err.value.status_code == 403
    assert repo.updated_to == []


def test_missing_order_returns_404():
    repo = _FakeOrdersRepo(None)

    with pytest.raises(HTTPException) as err:
        _run(UpdateOrderStatus(repo).execute(
            order_id=uuid4(), status=OrderStatus.accepted, actor_id=uuid4(), actor_role="admin",
        ))

    assert err.value.status_code == 404


def test_backwards_transition_returns_409():
    order = _order(status=OrderStatus.done)
    repo = _FakeOrdersRepo(order)

    with pytest.raises(HTTPException) as err:
        _run(UpdateOrderStatus(repo).execute(
            order_id=order.id, status=OrderStatus.created, actor_id=uuid4(), actor_role="admin",
        ))

    assert err.value.status_code == 409
    assert repo.updated_to == []

