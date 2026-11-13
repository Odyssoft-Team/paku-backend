"""Adicionales incompatibles (alternativas o trabajo repetido) y adicionales NO_DISPONIBLE elegidos a mano."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.cart.app.use_cases_impl.pricing import CartPricing
from app.modules.cart.domain.cart import CartItemKind
from app.modules.store.api.schemas import AddonOut
from app.modules.store.app.use_cases_impl.quote import price_service
from app.modules.store.domain.addon_conflicts import conflicts_of, first_conflict
from app.modules.store.domain.models import Addon, Product, Species
from app.modules.store.domain.recommendations import Rule

BATH = uuid4()
CORTE = uuid4()
RAPADO = uuid4()
RETOQUE = uuid4()
CARITA = uuid4()
LOC = uuid4()
EXT = uuid4()
CEPILLO = uuid4()
CODES = {CORTE: "ADD_CORTE_EST", RAPADO: "ADD_CORTE_CORTO", RETOQUE: "ADD_RETOQUE", CARITA: "ADD_CARITA",
         LOC: "ADD_DESMOTADO_LOC", EXT: "ADD_DESMOTADO_EXT", CEPILLO: "ADD_TOOTHBRUSH"}
NAMES = {CORTE: "Corte estético", RAPADO: "Rapado corporal con máquina", RETOQUE: "Retoque Paku",
         CARITA: "Retoque de carita", LOC: "Desmotado localizado", EXT: "Desmotado extendido",
         CEPILLO: "Cepillo dental personal"}


def _run(coro):
    return asyncio.run(coro)


class _Store:
    def __init__(self, rules=None):
        self.rules = rules or []
        self.product = Product(id=BATH, category_id=uuid4(), name="Fresco y Limpio", species=Species.dog,
                               allowed_breeds=None, is_active=True, code="Clásico")
        self.addons = {i: Addon(id=i, product_id=BATH, name=NAMES[i], species=Species.dog, allowed_breeds=None,
                                is_active=True, code=c) for i, c in CODES.items()}

    async def get_product(self, product_id):
        return self.product if product_id == BATH else None

    async def get_addon(self, addon_id):
        return self.addons.get(addon_id)

    async def price_category_for(self, breed_id):
        return "curly_no_undercoat"

    async def price_for(self, **kw):
        return 50.0

    async def list_recommendation_rules(self):
        return self.rules

    async def breed_coat_type(self, breed_id):
        return "curly_no_undercoat"

    async def list_products(self, *, category_id, species=None):
        return [self.product]

    async def list_addons(self, *, product_id):
        return list(self.addons.values())


class _Pets:
    def __init__(self, pet):
        self.pet = pet

    async def get_by_id(self, pet_id, include_deleted: bool = False):
        return self.pet


def _pet(weight=12.0):
    return SimpleNamespace(id=uuid4(), owner_id=uuid4(), species=Species.dog, breed_id="poodle", breed_name="Poodle",
                           weight_kg=weight, birth_date=None, skin_sensitivity=None)


def test_conflict_pairs():
    assert first_conflict(["ADD_CORTE_EST", "ADD_CORTE_CORTO"]) == ("ADD_CORTE_CORTO", "ADD_CORTE_EST")
    assert first_conflict(["ADD_DESMOTADO_LOC", "ADD_DESMOTADO_EXT"]) is not None
    assert first_conflict(["ADD_CARITA", "ADD_RETOQUE"]) is not None
    assert first_conflict(["ADD_CORTE_EST", "ADD_RETOQUE"]) is not None
    assert first_conflict(["ADD_CORTE_EST", "ADD_CARITA"]) is not None
    # Combinaciones válidas
    assert first_conflict(["ADD_CORTE_CORTO", "ADD_RETOQUE"]) is None
    assert first_conflict(["ADD_DESMOTADO_EXT", "ADD_CORTE_EST", "ADD_TOOTHBRUSH"]) is None
    assert first_conflict([None, "ADD_RETOQUE"]) is None   # sin código no participa
    assert conflicts_of("ADD_CORTE_EST") == ["ADD_CARITA", "ADD_CORTE_CORTO", "ADD_RETOQUE"]
    assert conflicts_of("ADD_TOOTHBRUSH") == [] and conflicts_of(None) == []


@pytest.mark.parametrize("a,b", [(CORTE, RAPADO), (LOC, EXT), (CARITA, RETOQUE), (CORTE, RETOQUE), (CORTE, CARITA)])
def test_quote_rejects_incompatible_addons(a, b):
    with pytest.raises(HTTPException) as err:
        _run(price_service(_Store(), pet=_pet(), product_id=BATH, addon_ids=[a, b, CEPILLO]))
    assert err.value.status_code == 422
    assert err.value.detail["code"] == "ADDONS_INCOMPATIBLE"
    assert NAMES[a] in err.value.detail["message"] and NAMES[b] in err.value.detail["message"]


def test_quote_accepts_compatible_addons():
    result = _run(price_service(_Store(), pet=_pet(), product_id=BATH, addon_ids=[RAPADO, RETOQUE, EXT, CEPILLO]))
    assert result.total == 250.0


def test_addon_out_lists_incompatible_codes():
    out = AddonOut(id=uuid4(), product_id=BATH, name="Corte estético", description=None, species=Species.dog,
                   allowed_breeds=None, is_active=True, code="ADD_CORTE_EST")
    assert out.incompatible_with == ["ADD_CARITA", "ADD_CORTE_CORTO", "ADD_RETOQUE"]


def _cart(pet, addon_id, answers):
    return [
        {"kind": CartItemKind.service_base, "ref_id": str(BATH), "name": None, "qty": 1, "unit_price": 1.0,
         "meta": {"pet_id": str(pet.id), "answers": answers}},
        {"kind": CartItemKind.service_addon, "ref_id": str(addon_id), "name": None, "qty": 1, "unit_price": 1.0,
         "meta": None},
    ]


NOT_OVER_25 = Rule(id="AR-032", kind="addon", priority=3, active=True, action="NO_DISPONIBLE",
                   conditions={"services": ["Clásico"], "min_weight_kg": 25.01, "question": "Q-STYLING",
                               "answer": "RETOUCH"}, target_code="ADD_RETOQUE")


def test_cart_rejects_addon_marked_unavailable():
    pet = _pet(weight=30.0)
    pricing = CartPricing(store_repo=_Store([NOT_OVER_25]), pets_repo=_Pets(pet))
    with pytest.raises(HTTPException) as err:
        _run(pricing.price_lines(_cart(pet, RETOQUE, {"Q-STYLING": "RETOUCH"}), user_id=pet.owner_id))
    assert err.value.detail["code"] == "ADDON_NOT_AVAILABLE"
    assert err.value.detail["addon_code"] == "ADD_RETOQUE"


def test_cart_allows_addon_when_rule_does_not_apply():
    pet = _pet(weight=12.0)
    pricing = CartPricing(store_repo=_Store([NOT_OVER_25]), pets_repo=_Pets(pet))
    lines = _run(pricing.price_lines(_cart(pet, RETOQUE, {"Q-STYLING": "RETOUCH"}), user_id=pet.owner_id))
    assert [line["unit_price"] for line in lines] == [50.0, 50.0]
