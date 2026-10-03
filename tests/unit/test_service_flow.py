"""Pedido 3 (pasos del servicio y addons realizados) y pedido 6 (fotos de la orden)."""
import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.app.use_cases_impl.service_flow import (
    AddOrderPhoto,
    ListOrderPhotos,
    MarkAddonDone,
    NextServiceStep,
)
from app.modules.orders.app.use_cases_impl.transitions import ArriveOrder, CompleteOrder
from app.modules.orders.domain.order import Order, OrderStatus
from app.modules.orders.domain.photo import OrderPhotoKind

GROOMER = uuid4()
NAILS = str(uuid4())


class _OrdersRepo:
    _session = None  # notificaciones best effort

    def __init__(self, order):
        self.order = order

    async def get_order_admin(self, *, id):
        return self.order if self.order.id == id else None

    async def set_status(self, *, id, status):
        self.order = replace(self.order, status=status)
        return self.order

    async def set_service_step(self, *, id, step, at):
        log = list(self.order.service_steps_log or []) + [{"step": step, "started_at": at.isoformat()}]
        self.order = replace(self.order, service_step=step, service_steps_log=log)
        return self.order

    async def mark_addon_done(self, *, id, addon_id, at):
        done = list(self.order.addons_done or []) + [{"addon_id": addon_id, "done_at": at.isoformat()}]
        self.order = replace(self.order, addons_done=done)
        return self.order


class _PhotosRepo:
    def __init__(self, kinds=()):
        self.kinds = set(kinds)
        self.added = []

    async def has_kind(self, order_id, kind):
        return kind in self.kinds

    async def add(self, photo):
        self.added.append(photo)
        return photo

    async def list_by_order(self, order_id):
        return list(self.added)


def _order(step=None, status=OrderStatus.in_service, addons=True, done=None):
    items = [{"kind": "service_base", "ref_id": str(uuid4()), "name": "Baño", "meta": {"pet_id": str(uuid4())}}]
    if addons:
        items.append({"kind": "service_addon", "ref_id": NAILS, "name": "Corte de uñas", "meta": {}})
    order = Order.new(user_id=uuid4(), items_snapshot=items, total_snapshot=80.0)
    return replace(order, status=status, groomer_id=GROOMER, service_step=step, addons_done=done)


def _run(coro):
    return asyncio.run(coro)


def _next(order, from_step, photos=(), actor=GROOMER, role="groomer"):
    repo = _OrdersRepo(order)
    out = _run(NextServiceStep(repo, _PhotosRepo(photos)).execute(
        order_id=order.id, from_step=from_step, actor_id=actor, actor_role=role,
    ))
    return out


def _conflict_code(fn):
    with pytest.raises(HTTPException) as err:
        fn()
    assert err.value.status_code == 409
    return err.value.detail["code"]


def test_arrive_starts_reception():
    order = _order(status=OrderStatus.on_the_way)
    repo = _OrdersRepo(order)

    out = _run(ArriveOrder(repo).execute(order_id=order.id, groomer_id=GROOMER))

    assert out.status == OrderStatus.in_service
    assert out.service_step == "reception"
    assert out.service_steps_log[0]["step"] == "reception"


def test_reception_needs_initial_photo():
    assert _conflict_code(lambda: _next(_order("reception"), "reception")) == "INITIAL_PHOTO_REQUIRED"
    assert _next(_order("reception"), "reception", photos=[OrderPhotoKind.initial]).service_step == "bath"


def test_double_tap_does_not_advance_twice():
    assert _conflict_code(lambda: _next(_order("drying"), "bath")) == "STEP_MISMATCH"


def test_finishing_needs_purchased_addons_done():
    assert _conflict_code(lambda: _next(_order("finishing"), "finishing")) == "ADDONS_PENDING"
    done = [{"addon_id": NAILS, "done_at": "2026-10-10T10:00:00+00:00"}]
    assert _next(_order("finishing", done=done), "finishing").service_step == "return"


def test_return_closes_with_complete_only():
    assert _conflict_code(lambda: _next(_order("return"), "return")) == "LAST_STEP"


def test_next_step_requires_in_service_and_assigned_groomer():
    assert _conflict_code(lambda: _next(_order("bath", status=OrderStatus.on_the_way), "bath")) == "NOT_IN_SERVICE"
    with pytest.raises(HTTPException) as err:
        _next(_order("bath"), "bath", actor=uuid4())
    assert err.value.status_code == 403


def test_complete_requires_return_step():
    order = _order("drying")
    assert _conflict_code(lambda: _run(CompleteOrder(_OrdersRepo(order)).execute(
        order_id=order.id, groomer_id=GROOMER))) == "SERVICE_STEPS_PENDING"

    order_return = _order("return")
    out = _run(CompleteOrder(_OrdersRepo(order_return)).execute(order_id=order_return.id, groomer_id=GROOMER))
    assert out.status == OrderStatus.done


def test_complete_allows_orders_started_before_steps_existed():
    order = _order(step=None)
    out = _run(CompleteOrder(_OrdersRepo(order)).execute(order_id=order.id, groomer_id=GROOMER))
    assert out.status == OrderStatus.done


# --- addons realizados -----------------------------------------------------

def _mark(order, addon_id=NAILS):
    repo = _OrdersRepo(order)
    out = _run(MarkAddonDone(repo).execute(order_id=order.id, addon_id=addon_id, actor_id=GROOMER, actor_role="groomer"))
    return out


def test_mark_addon_done_is_idempotent():
    out = _mark(_order("bath"))
    assert [a["addon_id"] for a in out.addons_done] == [NAILS]
    again = _mark(out)
    assert len(again.addons_done) == 1


def test_mark_unknown_addon_returns_404():
    with pytest.raises(HTTPException) as err:
        _mark(_order("bath"), addon_id=str(uuid4()))
    assert err.value.status_code == 404


def test_mark_addon_outside_grooming_steps_returns_409():
    assert _conflict_code(lambda: _mark(_order("reception"))) == "ADDON_NOT_ALLOWED_NOW"


# --- fotos -----------------------------------------------------------------

def test_add_photo_validates_object_belongs_to_order():
    order = _order("reception")
    photos = _PhotosRepo()
    use_case = AddOrderPhoto(_OrdersRepo(order), photos)
    good = f"orders/{order.id}/photo_20261010T100000123456Z.jpg"

    photo = _run(use_case.execute(order_id=order.id, object_name=good, kind=OrderPhotoKind.initial, note=None,
                                  actor_id=GROOMER, actor_role="groomer"))
    assert photo.kind == OrderPhotoKind.initial

    other = f"orders/{uuid4()}/photo_20261010T100000123456Z.jpg"
    with pytest.raises(HTTPException) as err:
        _run(use_case.execute(order_id=order.id, object_name=other, kind=OrderPhotoKind.final, note=None,
                              actor_id=GROOMER, actor_role="groomer"))
    assert err.value.status_code == 403


def test_list_photos_for_owner_groomer_admin_only():
    order = _order("bath")
    use_case = ListOrderPhotos(_OrdersRepo(order), _PhotosRepo())
    for actor, role in [(order.user_id, "user"), (GROOMER, "groomer"), (uuid4(), "admin")]:
        assert _run(use_case.execute(order_id=order.id, actor_id=actor, actor_role=role)) == []
    with pytest.raises(HTTPException) as err:
        _run(use_case.execute(order_id=order.id, actor_id=uuid4(), actor_role="user"))
    assert err.value.status_code == 403
