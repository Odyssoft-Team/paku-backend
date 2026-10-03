"""Pedido 2: ruta del groomer por día (hora de Lima), detalle de parada y datos de mascota/cliente/servicio."""
import asyncio
from dataclasses import replace
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.app.use_cases_impl.admin_orders import GetGroomerOrder, ListGroomerOrders, lima_day_range
from app.modules.orders.app.use_cases_impl.groomer_view import build_groomer_view, purchased_addons
from app.modules.orders.domain.order import Order


def test_lima_day_range_is_utc_minus_5():
    start, end = lima_day_range(date(2026, 10, 10))
    assert start.astimezone(timezone.utc) == datetime(2026, 10, 10, 5, 0, tzinfo=timezone.utc)
    assert end.astimezone(timezone.utc) == datetime(2026, 10, 11, 5, 0, tzinfo=timezone.utc)


def test_list_passes_lima_day_range_to_repo():
    captured = {}

    class _Repo:
        async def list_orders_by_groomer(self, **kwargs):
            captured.update(kwargs)
            return []

    groomer_id = uuid4()
    asyncio.run(ListGroomerOrders(_Repo()).execute(groomer_id=groomer_id, day=date(2026, 10, 10)))

    assert captured["groomer_id"] == groomer_id
    assert captured["scheduled_from"] == lima_day_range(date(2026, 10, 10))[0]
    assert captured["scheduled_to"] == lima_day_range(date(2026, 10, 10))[1]


def _order(**overrides):
    pet_id = uuid4()
    nails = uuid4()
    items = [
        {"kind": "service_base", "ref_id": str(uuid4()), "name": "Baño completo", "qty": 1, "unit_price": 65.0,
         "meta": {"pet_id": str(pet_id)}},
        {"kind": "service_addon", "ref_id": str(nails), "name": "Corte de uñas", "qty": 1, "unit_price": 15.0,
         "meta": {"pet_id": str(pet_id)}},
    ]
    order = Order.new(user_id=uuid4(), items_snapshot=items, total_snapshot=80.0)
    return replace(order, **overrides), pet_id, nails


class _Repo:
    def __init__(self, order):
        self.order = order

    async def get_order_admin(self, *, id):
        return self.order if self.order and self.order.id == id else None


def test_get_assignment_only_for_assigned_groomer():
    groomer_id = uuid4()
    order, _, _ = _order(groomer_id=groomer_id)

    out = asyncio.run(GetGroomerOrder(_Repo(order)).execute(order_id=order.id, groomer_id=groomer_id, role="groomer"))
    assert out is order

    with pytest.raises(HTTPException) as err:
        asyncio.run(GetGroomerOrder(_Repo(order)).execute(order_id=order.id, groomer_id=uuid4(), role="groomer"))
    assert err.value.status_code == 403

    with pytest.raises(HTTPException) as err:
        asyncio.run(GetGroomerOrder(_Repo(None)).execute(order_id=uuid4(), groomer_id=groomer_id, role="groomer"))
    assert err.value.status_code == 404


def test_purchased_addons_supports_lines_and_legacy_meta():
    legacy_addon = uuid4()
    order, _, nails = _order()
    order.items_snapshot[0]["meta"]["addon_ids"] = [str(legacy_addon), str(nails)]

    assert purchased_addons(order) == [
        {"id": str(nails), "name": "Corte de uñas"},
        {"id": str(legacy_addon), "name": None},
    ]


def test_build_groomer_view_joins_pet_client_and_service():
    order, pet_id, nails = _order()
    pet = SimpleNamespace(
        id=pet_id, name="Firulais", species="dog", breed_name="Labrador", sex="male", birth_date=date(2020, 1, 1),
        weight_kg=15.0, photo_url="pets/x.jpg", notes="muerde", skin_sensitivity=True, bath_behavior="calm",
        tolerates_drying=False, tolerates_nail_clipping=True, special_shampoo=None,
    )
    user = SimpleNamespace(first_name="Ana", last_name="Pérez", phone="999888777")

    class _Pets:
        async def get_by_id(self, pid, include_deleted=False):
            return pet if pid == pet_id else None

    class _Users:
        async def get_by_id(self, uid):
            return user

    class _Store:
        async def get_addon(self, addon_id):
            return None

    view = asyncio.run(build_groomer_view(
        order, pets_repo=_Pets(), users_repo=_Users(), store_repo=_Store(), signed_url=lambda k: f"signed:{k}",
    ))

    assert view["pet"]["name"] == "Firulais"
    assert view["pet"]["photo_url"] == "signed:pets/x.jpg"
    assert view["client"] == {"first_name": "Ana", "last_name": "Pérez", "phone": "999888777"}
    assert view["service"] == {"name": "Baño completo", "addons": [{"id": str(nails), "name": "Corte de uñas"}]}
