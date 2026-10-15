"""Feature 0004 — precios por tipo de pelaje: categoría de precio, cotización, tabla y simulador."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.store.app.use_cases_impl.admin import CreatePriceRule
from app.modules.store.app.use_cases_impl.pricing_admin import (
    ReplacePriceMatrix,
    SimulatePrices,
    pricing_config,
    validate_matrix,
)
from app.modules.store.app.use_cases_impl.quote import price_service
from app.modules.store.domain.models import Addon, Product, Species
from app.modules.catalog.domain.breeds_data import BREEDS_CATALOG
from app.modules.store.domain.pricing import FALLBACK_CATEGORY, category_for_coat

_COAT = {b["id"]: b.get("coat_type") for g in BREEDS_CATALOG for b in g["breeds"]}


def price_category(breed_id, breed_name=None):
    """Misma regla que PostgresStoreRepository.price_category_for, con el catálogo semilla."""
    return category_for_coat(_COAT.get((breed_id or "").strip().lower()))

CATEGORY = uuid4()
CLASICO = uuid4()
PREMIUM = uuid4()
NAILS = uuid4()


def run(coro):
    return asyncio.run(coro)


# ─── Categoría de precio ──────────────────────────────────────────────────────


def test_price_category_uses_breed_coat_type():
    assert price_category("labrador") == "double_short"
    assert price_category("poodle") == "curly_no_undercoat"
    assert price_category("shih_tzu") == "simple_medium_long"
    assert price_category("goldendoodle") == "mixed_curly_undercoat"
    assert price_category(" Golden_Retriever ") == "double_long"


def test_price_category_falls_back_to_mestizo():
    assert price_category("dog_mixed") == FALLBACK_CATEGORY
    assert price_category(None, "Cruce de calle") == FALLBACK_CATEGORY
    assert price_category(None, None) == FALLBACK_CATEGORY
    assert price_category("raza_inexistente") == FALLBACK_CATEGORY
    assert price_category("persian") == FALLBACK_CATEGORY  # gatos: sin pelaje en el catálogo


# ─── Repositorio falso ────────────────────────────────────────────────────────


class FakeRepo:
    """Reglas: {(target_id, categoría): precio}. Con respaldo a "mestizo" como el repo real."""

    def __init__(self, rules=None):
        self.rules = rules or {}
        self.asked = []
        self.replaced = None
        self.products = {
            CLASICO: Product(id=CLASICO, category_id=CATEGORY, name="Clásico", species=Species.dog,
                             allowed_breeds=None, is_active=True),
            PREMIUM: Product(id=PREMIUM, category_id=CATEGORY, name="Premium", species=Species.dog,
                             allowed_breeds=["poodle"], is_active=True),
        }
        self.addons = {
            NAILS: Addon(id=NAILS, product_id=CLASICO, name="Corte de uñas", species=Species.dog,
                         allowed_breeds=None, is_active=True),
        }

    async def price_category_for(self, breed_id):
        return price_category(breed_id)

    async def get_product(self, product_id):
        return self.products.get(product_id)

    async def get_addon(self, addon_id):
        return self.addons.get(addon_id)

    async def list_products(self, *, category_id, species=None):
        return [p for p in self.products.values() if p.category_id == category_id]

    async def list_addons(self, *, product_id):
        return [a for a in self.addons.values() if a.product_id == product_id]

    async def price_detail_for(self, *, target_id, target_type, species, breed_category, weight):
        self.asked.append(breed_category)
        if (target_id, breed_category) in self.rules:
            return self.rules[(target_id, breed_category)], breed_category
        if (target_id, "mestizo") in self.rules:
            return self.rules[(target_id, "mestizo")], "mestizo"
        return None, None

    async def price_for(self, **kw):
        return (await self.price_detail_for(**kw))[0]

    async def replace_price_rules(self, *, target_id, target_type, species, rules, currency="PEN"):
        self.replaced = dict(target_id=target_id, target_type=target_type, species=species, rules=rules)
        return []


def _pet(breed_id, weight=12.0, breed_name=None):
    return SimpleNamespace(id=uuid4(), species=Species.dog, breed_id=breed_id, breed_name=breed_name,
                           weight_kg=weight)


# ─── Cotización ───────────────────────────────────────────────────────────────


def test_quote_uses_coat_type_rule():
    repo = FakeRepo({(CLASICO, "double_short"): 110.0, (CLASICO, "mestizo"): 90.0})
    result = run(price_service(repo, pet=_pet("labrador"), product_id=CLASICO))
    assert result.product.price == 110.0
    assert repo.asked[0] == "double_short"


def test_quote_mestizo_and_missing_coat_use_mestizo_row():
    repo = FakeRepo({(CLASICO, "mestizo"): 90.0})
    assert run(price_service(repo, pet=_pet("dog_mixed"), product_id=CLASICO)).product.price == 90.0
    # Labrador sin fila de su pelaje → respaldo "mestizo" (nunca queda sin precio si existe)
    assert run(price_service(repo, pet=_pet("labrador"), product_id=CLASICO)).product.price == 90.0


# ─── Validación de la tabla ───────────────────────────────────────────────────


def _cell(cat, lo, hi, price=80.0):
    return {"breed_category": cat, "weight_min": lo, "weight_max": hi, "price": price}


def test_validate_matrix_ok():
    validate_matrix([
        _cell("simple_short", 0, 5), _cell("simple_short", 5.01, 15), _cell("simple_short", 15.01, None),
        _cell("mestizo", 0, None),
    ])


@pytest.mark.parametrize(
    "cells, code",
    [
        ([_cell("official", 0, 5)], "PRICE_CATEGORY_INVALID"),
        ([_cell("simple_short", 0, 5, price=-1)], "PRICE_INVALID"),
        ([_cell("simple_short", 10, 5)], "WEIGHT_RANGE_INVALID"),
        ([_cell("simple_short", 0, 10), _cell("simple_short", 8, 20)], "WEIGHT_RANGE_OVERLAP"),
        ([_cell("simple_short", 0, None), _cell("simple_short", 20, 30)], "WEIGHT_RANGE_OVERLAP"),
    ],
)
def test_validate_matrix_errors(cells, code):
    with pytest.raises(HTTPException) as exc:
        validate_matrix(cells)
    assert exc.value.status_code == 422 and exc.value.detail["code"] == code


def test_replace_matrix_uses_target_species_and_validates():
    repo = FakeRepo()
    run(ReplacePriceMatrix(repo=repo).execute(
        target_id=NAILS, target_type="addon", cells=[_cell("mestizo", 0, None, 15.0)],
    ))
    assert repo.replaced["species"] == Species.dog and repo.replaced["target_type"] == "addon"

    with pytest.raises(HTTPException) as exc:
        run(ReplacePriceMatrix(repo=repo).execute(target_id=uuid4(), target_type="product", cells=[]))
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        run(ReplacePriceMatrix(repo=repo).execute(target_id=CLASICO, target_type="otro", cells=[]))
    assert exc.value.status_code == 422


def test_create_single_rule_accepts_coat_types_only():
    repo = FakeRepo()
    with pytest.raises(HTTPException) as exc:
        run(CreatePriceRule(repo=repo).execute(
            target_id=CLASICO, target_type="product", species=Species.dog, breed_category="official",
            weight_min=0, weight_max=5, price=80,
        ))
    assert exc.value.status_code == 422


# ─── Simulador ────────────────────────────────────────────────────────────────


def test_simulation_reports_category_fallback_and_breed_filter():
    repo = FakeRepo({
        (CLASICO, "double_short"): 110.0,
        (CLASICO, "mestizo"): 90.0,
        (NAILS, "mestizo"): 15.0,
    })
    result = run(SimulatePrices(repo=repo).execute(
        category_id=CATEGORY, species=Species.dog, weight=20, breed_id="labrador",
    ))
    assert result.price_category == "double_short"
    assert result.price_category_label == "Doble manto corto"
    names = [p.name for p in result.products]
    assert names == ["Clásico"]  # Premium solo para poodle
    clasico = result.products[0]
    assert clasico.price == 110.0 and clasico.used_fallback is False
    nails = clasico.addons[0]
    assert nails.price == 15.0 and nails.used_fallback is True and nails.category_used == "mestizo"


def test_simulation_rejects_invalid_weight():
    with pytest.raises(HTTPException):
        run(SimulatePrices(repo=FakeRepo()).execute(category_id=CATEGORY, species=Species.dog, weight=0))


def test_pricing_config_lists_rows_and_tiers():
    cfg = pricing_config()
    assert [c["key"] for c in cfg["categories"]][-1] == "mestizo"
    assert len(cfg["categories"]) == 7
    assert cfg["weight_tiers"][0] == {"weight_min": 0, "weight_max": 5}
    assert cfg["weight_tiers"][-1]["weight_max"] is None
