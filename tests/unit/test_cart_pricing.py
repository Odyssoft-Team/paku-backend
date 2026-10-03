"""Precios del carrito calculados por el backend (store), formato único de addons y PRICE_CHANGED."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.cart.app.use_cases_impl.cart import Checkout
from app.modules.cart.app.use_cases_impl.pricing import CartPricing
from app.modules.cart.domain.cart import CartItem, CartItemKind, CartSession, CartStatus
from app.modules.store.domain.models import Addon, Product, Species

BATH = uuid4()
NAILS = uuid4()
DENTAL_OTHER_SERVICE = uuid4()
OTHER_SERVICE = uuid4()


class _FakeStore:
    def __init__(self, prices=None, product_breeds=None):
        self.prices = prices or {BATH: 65.0, NAILS: 15.0, DENTAL_OTHER_SERVICE: 20.0}
        self.products = {
            BATH: Product(id=BATH, category_id=uuid4(), name="Baño completo", species=Species.dog,
                          allowed_breeds=product_breeds, is_active=True),
        }
        self.addons = {
            NAILS: Addon(id=NAILS, product_id=BATH, name="Corte de uñas", species=Species.dog,
                         allowed_breeds=None, is_active=True),
            DENTAL_OTHER_SERVICE: Addon(id=DENTAL_OTHER_SERVICE, product_id=OTHER_SERVICE, name="Limpieza dental",
                                        species=Species.dog, allowed_breeds=None, is_active=True),
        }

    async def get_product(self, product_id):
        return self.products.get(product_id)

    async def get_addon(self, addon_id):
        return self.addons.get(addon_id)

    async def price_for(self, *, target_id, target_type, species, breed_category, weight):
        return self.prices.get(target_id)


class _FakePets:
    def __init__(self, pet):
        self.pet = pet

    async def get_by_id(self, pet_id, include_deleted: bool = False):
        return self.pet if self.pet and self.pet.id == pet_id else None


def _pet(owner_id, weight=15.0, breed_id="labrador"):
    return SimpleNamespace(id=uuid4(), owner_id=owner_id, species=Species.dog, breed_id=breed_id,
                           breed_name="Labrador", weight_kg=weight)


def _base(pet_id, price=1.0):
    return {"kind": CartItemKind.service_base, "ref_id": str(BATH), "name": "lo que sea", "qty": 1,
            "unit_price": price,
            "meta": {"pet_id": str(pet_id), "scheduled_date": "2026-10-10", "scheduled_time": "10:00"}}


def _addon(addon_id=NAILS, price=0.5, meta=None):
    return {"kind": CartItemKind.service_addon, "ref_id": str(addon_id), "name": None, "qty": 1,
            "unit_price": price, "meta": meta}


def _run(coro):
    return asyncio.run(coro)


def test_server_prices_and_names_replace_client_values():
    user = uuid4()
    pet = _pet(user)
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(pet))

    out = _run(pricing.price_lines(
        [_base(pet.id, price=1.0), _addon(price=0.5, meta={"requires_base": "otro-id"})], user_id=user,
    ))

    assert [l["unit_price"] for l in out] == [65.0, 15.0]
    assert [l["name"] for l in out] == ["Baño completo", "Corte de uñas"]
    assert out[1]["meta"]["pet_id"] == str(pet.id)  # el backend liga el addon a la mascota


def test_physical_products_are_rejected():
    user = uuid4()
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(None))

    with pytest.raises(HTTPException) as err:
        _run(pricing.price_lines([{"kind": CartItemKind.product, "ref_id": "p1", "qty": 1}], user_id=user))

    assert err.value.status_code == 422
    assert err.value.detail["code"] == "PRODUCT_NOT_SUPPORTED"


def test_addon_without_base_service_is_rejected():
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(None))

    with pytest.raises(HTTPException) as err:
        _run(pricing.price_lines([_addon()], user_id=uuid4()))

    assert err.value.status_code == 400
    assert err.value.detail["code"] == "BASE_SERVICE_REQUIRED"


def test_addon_of_another_service_is_rejected():
    user = uuid4()
    pet = _pet(user)
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(pet))

    with pytest.raises(HTTPException) as err:
        _run(pricing.price_lines([_base(pet.id), _addon(DENTAL_OTHER_SERVICE)], user_id=user))

    assert err.value.status_code == 400
    assert err.value.detail["reason"] == "not_in_product"


def test_duplicate_addon_is_rejected():
    user = uuid4()
    pet = _pet(user)
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(pet))

    with pytest.raises(HTTPException) as err:
        _run(pricing.price_lines([_base(pet.id), _addon(), _addon()], user_id=user))

    assert err.value.detail["code"] == "DUPLICATE_ADDON"


def test_pet_of_another_user_is_rejected():
    pet = _pet(uuid4())
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(pet))

    with pytest.raises(HTTPException) as err:
        _run(pricing.price_lines([_base(pet.id)], user_id=uuid4()))

    assert err.value.status_code == 403


def test_pet_without_weight_cannot_be_priced():
    user = uuid4()
    pet = _pet(user, weight=None)
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(pet))

    with pytest.raises(HTTPException) as err:
        _run(pricing.price_lines([_base(pet.id)], user_id=user))

    assert err.value.status_code == 422


def test_breed_not_allowed_is_rejected():
    user = uuid4()
    pet = _pet(user, breed_id="labrador")
    pricing = CartPricing(store_repo=_FakeStore(product_breeds=["Poodle"]), pets_repo=_FakePets(pet))

    with pytest.raises(HTTPException) as err:
        _run(pricing.price_lines([_base(pet.id)], user_id=user))

    assert err.value.status_code == 400


def test_breed_allowed_matches_id_or_name():
    user = uuid4()
    pet = _pet(user, breed_id="labrador")
    for allowed in (["labrador"], ["LABRADOR "], ["Labrador"]):
        pricing = CartPricing(store_repo=_FakeStore(product_breeds=allowed), pets_repo=_FakePets(pet))
        out = _run(pricing.price_lines([_base(pet.id)], user_id=user))
        assert out[0]["unit_price"] == 65.0


# --- checkout -------------------------------------------------------------

class _FakeCartRepo:
    def __init__(self, user_id, items):
        self.user_id = user_id
        self.items = items
        self.updated = None
        self.checked_out = False

    async def get_cart(self, cart_id, user_id):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return CartSession(id=cart_id, user_id=user_id, status=CartStatus.active, expires_at=now,
                           created_at=now, updated_at=now)

    async def list_items(self, cart_id, user_id):
        return self.items

    async def update_item_prices(self, *, cart_id, prices):
        self.updated = prices

    async def checkout(self, cart_id, user_id):
        self.checked_out = True
        return await self.get_cart(cart_id, user_id)


def _cart_item(cart_id, line, unit_price, name):
    return CartItem(id=uuid4(), cart_id=cart_id, kind=line["kind"], ref_id=line["ref_id"], name=name,
                    qty=1, unit_price=unit_price, meta=line["meta"])


def test_checkout_with_current_prices_goes_through():
    user = uuid4()
    pet = _pet(user)
    cart_id = uuid4()
    nails_meta = {"pet_id": str(pet.id)}
    items = [_cart_item(cart_id, _base(pet.id), 65.0, "Baño completo"),
             _cart_item(cart_id, _addon(meta=nails_meta), 15.0, "Corte de uñas")]
    repo = _FakeCartRepo(user, items)
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(pet))

    _run(Checkout(repo=repo, pricing=pricing).execute(cart_id=cart_id, user_id=user))

    assert repo.checked_out
    assert repo.updated is None


def test_checkout_with_changed_price_returns_409_and_saves_new_prices():
    user = uuid4()
    pet = _pet(user)
    cart_id = uuid4()
    items = [_cart_item(cart_id, _base(pet.id), 60.0, "Baño completo")]  # se agregó cuando costaba 60
    repo = _FakeCartRepo(user, items)
    pricing = CartPricing(store_repo=_FakeStore(), pets_repo=_FakePets(pet))  # hoy cuesta 65

    with pytest.raises(HTTPException) as err:
        _run(Checkout(repo=repo, pricing=pricing).execute(cart_id=cart_id, user_id=user))

    assert err.value.status_code == 409
    detail = err.value.detail
    assert detail["code"] == "PRICE_CHANGED"
    assert detail["total"] == 65.0
    assert detail["items"][0]["old_unit_price"] == 60.0
    assert detail["items"][0]["new_unit_price"] == 65.0
    assert repo.updated[items[0].id][0] == 65.0
    assert not repo.checked_out
