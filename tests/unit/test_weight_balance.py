"""Feature 0003-saldo-por-peso: peso declarado, peso medido, bloqueo del peso y saldo pendiente."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.orders.api.schemas import OrderOut
from app.modules.orders.app.use_cases_impl import weight_balance
from app.modules.orders.app.use_cases_impl.groomer_view import build_groomer_view
from app.modules.orders.domain.order import Order, OrderStatus, PaymentStatus
from app.modules.pet_records.app.use_cases_impl.create_record import CreateRecord
from app.modules.pet_records.domain.record import RecordType
from app.modules.pets.domain.pet import Pet, Species

SERVICE_ID = uuid4()


def _run(coro):
    return asyncio.run(coro)


def _pet(weight=17.0) -> Pet:
    return Pet(
        id=uuid4(), owner_id=uuid4(), name="Rocky", species=Species.dog, breed_id="labrador",
        breed_name="Labrador", sex=None, birth_date=None, notes=None,
        created_at=datetime.now(timezone.utc), weight_kg=weight,
    )


def _order(pet: Pet, *, declared=15.0, price=90.0, **fields) -> Order:
    meta = {"pet_id": str(pet.id)}
    if declared is not None:
        meta["pet_weight_kg"] = declared
    base = {"kind": "service_base", "ref_id": str(SERVICE_ID), "name": "Baño", "qty": 1,
            "unit_price": price, "meta": meta}
    order = Order.new(user_id=pet.owner_id, items_snapshot=[base], total_snapshot=price)
    return replace(order, status=OrderStatus.in_service, payment_status=PaymentStatus.paid, **fields)


class _Store:
    """Precio por peso: hasta 15 kg S/90, más de 15 kg S/95."""

    async def price_category_for(self, breed_id):
        from app.modules.catalog.domain.breeds_data import BREEDS_CATALOG
        from app.modules.store.domain.pricing import category_for_coat
        coats = {b["id"]: b.get("coat_type") for g in BREEDS_CATALOG for b in g["breeds"]}
        return category_for_coat(coats.get((breed_id or "").strip().lower()))

    async def price_for(self, *, target_id, target_type, species, breed_category, weight):
        return 90.0 if weight <= 15 else 95.0


class _Orders:
    def __init__(self, order=None, *, locked=(), unpaid=()):
        self.order = order
        self.locked = set(locked)
        self.unpaid = list(unpaid)
        self.measure_calls = []
        self.find_calls = []
        self._session = None

    async def find_order_for_measurement(self, *, pet_id, groomer_id):
        self.find_calls.append(groomer_id)
        return self.order

    async def set_measured_weight(self, *, id, weight_kg, at, extra_charge):
        self.measure_calls.append((weight_kg, extra_charge))
        self.order = replace(self.order, measured_weight_kg=weight_kg, measured_weight_at=at, extra_charge=extra_charge)
        return self.order

    async def pets_with_requested_service(self, *, pet_ids):
        return {p for p in pet_ids if p in self.locked}

    async def list_unpaid_adjustments(self, *, user_id):
        return self.unpaid


class _Pets:
    def __init__(self, pet):
        self.pet = pet
        self.updated = None

    async def get_by_id(self, pet_id, include_deleted=False):
        return self.pet

    async def update(self, pet):
        self.updated = pet
        self.pet = pet
        return pet


class _Records:
    async def create(self, record):
        return record


@pytest.fixture
def notices(monkeypatch):
    sent = []

    async def _notify_user(_repo, **kwargs):
        sent.append(("user", kwargs))

    async def _notify_admins(_repo, _users, **kwargs):
        sent.append(("admins", kwargs))

    monkeypatch.setattr(weight_balance, "notify_user", _notify_user)
    monkeypatch.setattr(weight_balance, "_notify_admins", _notify_admins)
    return sent


def _measure(orders, pet, weight, *, role="groomer", actor_id=None):
    return _run(weight_balance.register_measured_weight(
        orders_repo=orders, store_repo=_Store(), users_repo=object(), pet=pet, weight_kg=weight,
        actor_id=actor_id or uuid4(), actor_role=role,
    ))


# --- Peso medido en el servicio ---

def test_heavier_pet_stores_weight_without_charge(notices):
    # Feature 0008 (BR-029): se respeta el precio pagado; el peso real queda para el futuro
    pet = _pet(17.0)
    orders = _Orders(_order(pet))

    check = _measure(orders, pet, 17.0)

    assert check is None
    assert orders.order.measured_weight_kg == 17.0
    assert orders.order.extra_charge is None
    assert notices == []


def test_lighter_or_same_price_stores_weight_without_charge(notices):
    pet = _pet(12.0)
    orders = _Orders(_order(pet))

    _measure(orders, pet, 12.0)

    assert orders.order.measured_weight_kg == 12.0
    assert orders.order.extra_charge is None
    assert notices == []


def test_groomer_only_measures_own_orders_admin_any(notices):
    pet = _pet()
    orders = _Orders(_order(pet))
    groomer = uuid4()

    _measure(orders, pet, 17.0, role="groomer", actor_id=groomer)
    _measure(orders, pet, 17.0, role="admin")

    assert orders.find_calls == [groomer, None]


def test_measuring_twice_never_notifies_a_charge(notices):
    pet = _pet()
    orders = _Orders(_order(pet))

    _measure(orders, pet, 17.0)
    _measure(orders, pet, 18.0)

    assert notices == [] and orders.order.measured_weight_kg == 18.0


def test_order_with_adjustment_is_not_changed(notices):
    pet = _pet()
    orders = _Orders(_order(pet, extra_charge=5.0, adjustment_order_id=uuid4()))

    _measure(orders, pet, 20.0)

    assert orders.measure_calls == []
    assert notices == []


def test_without_order_in_service_nothing_is_stored(notices):
    pet = _pet()
    orders = _Orders(None)

    assert _measure(orders, pet, 17.0) is None
    assert orders.measure_calls == []


# --- Bloqueo del peso para el dueño (POST /pets/{id}/records) ---

def _record(pet, orders, *, role, user_id):
    use_case = CreateRecord(records_repo=_Records(), pets_repo=_Pets(pet), orders_repo=orders, store_repo=_Store())
    return _run(use_case.execute(
        pet_id=pet.id, user_id=user_id, role=role, type=RecordType.weight_record,
        occurred_at=datetime.now(timezone.utc), data={"weight_kg": 18.0},
    ))


def test_owner_cannot_change_weight_with_requested_service():
    pet = _pet()
    orders = _Orders(locked=[pet.id])

    with pytest.raises(HTTPException) as err:
        _record(pet, orders, role="user", user_id=pet.owner_id)

    assert err.value.status_code == 409
    assert err.value.detail["code"] == "PET_WEIGHT_LOCKED"


def test_owner_changes_weight_without_requested_service():
    pet = _pet()
    orders = _Orders()

    result = _record(pet, orders, role="user", user_id=pet.owner_id)

    assert result.price_check is None
    assert orders.find_calls == []  # el dueño no registra peso de servicio


def test_owner_waits_30_days_between_weight_changes():
    # Feature 0006: el dueño cambia el peso una vez cada 30 días; el primer cambio es libre.
    pet = replace(_pet(), weight_updated_at=datetime.now(timezone.utc) - timedelta(days=10))
    with pytest.raises(HTTPException) as err:
        _record(pet, _Orders(), role="user", user_id=pet.owner_id)
    assert err.value.status_code == 409
    assert err.value.detail["code"] == "PET_WEIGHT_COOLDOWN"

    old = replace(_pet(), weight_updated_at=datetime.now(timezone.utc) - timedelta(days=31))
    pets = _Pets(old)
    use_case = CreateRecord(records_repo=_Records(), pets_repo=pets, orders_repo=_Orders(), store_repo=_Store())
    _run(use_case.execute(
        pet_id=old.id, user_id=old.owner_id, role="user", type=RecordType.weight_record,
        occurred_at=datetime.now(timezone.utc), data={"weight_kg": 18.0},
    ))
    assert pets.updated.weight_kg == 18.0 and pets.updated.weight_updated_at is not None


def test_groomer_changes_weight_during_cooldown(notices):
    pet = replace(_pet(), weight_updated_at=datetime.now(timezone.utc) - timedelta(days=1))
    orders = _Orders(_order(pet))
    result = _record(pet, orders, role="admin", user_id=uuid4())
    assert result.price_check is None and orders.order.measured_weight_kg == 18.0


def test_admin_records_weight_even_if_locked(notices):
    pet = _pet()
    orders = _Orders(_order(pet), locked=[pet.id])

    result = _record(pet, orders, role="admin", user_id=uuid4())

    assert result.price_check is None
    assert orders.order.measured_weight_kg == 18.0 and orders.order.extra_charge is None


# --- Saldo pendiente ---

def test_pending_balance_sums_unpaid_adjustments():
    pet = _pet()
    unpaid = [replace(_order(pet), total_snapshot=5.0), replace(_order(pet), total_snapshot=3.5)]

    amount, currency, orders = _run(weight_balance.pending_balance(_Orders(unpaid=unpaid), user_id=pet.owner_id))

    assert (amount, currency, len(orders)) == (8.5, "PEN", 2)


def test_pending_balance_blocks_new_services():
    pet = _pet()
    orders = _Orders(unpaid=[replace(_order(pet), total_snapshot=5.0)])

    with pytest.raises(HTTPException) as err:
        _run(weight_balance.assert_no_pending_balance(orders, user_id=pet.owner_id))

    assert err.value.status_code == 409
    assert err.value.detail["code"] == "PENDING_BALANCE"
    assert err.value.detail["amount"] == 5.0


def test_no_balance_lets_client_continue():
    _run(weight_balance.assert_no_pending_balance(_Orders(), user_id=uuid4()))


# --- Peso declarado en la orden y en la vista del groomer ---

class _Users:
    async def get_by_id(self, _id):
        return None


def _groomer_pet(order, pet):
    view = _run(build_groomer_view(
        order, pets_repo=_Pets(pet), users_repo=_Users(), store_repo=None, signed_url=lambda _x: None,
    ))
    return view["pet"]


def test_groomer_sees_declared_weight_not_current():
    pet = _pet(17.0)  # el cliente cambió el peso después de comprar

    assert _groomer_pet(_order(pet, declared=15.0), pet)["weight_kg"] == 15.0


def test_old_orders_fall_back_to_current_weight():
    pet = _pet(17.0)

    assert _groomer_pet(_order(pet, declared=None), pet)["weight_kg"] == 17.0


def test_order_out_exposes_declared_weight():
    pet = _pet()
    out = OrderOut(**_order(pet, extra_charge=5.0, measured_weight_kg=17.0).__dict__)

    assert out.declared_weight_kg == 15.0
    assert out.measured_weight_kg == 17.0
    assert out.extra_charge == 5.0
