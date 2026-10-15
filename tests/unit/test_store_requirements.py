"""Feature 0005 — requisitos del servicio (peso/edad), ocultar lo que no aplica y razas del documento."""
import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.store.app.use_cases_impl.catalog import GetProduct, ListProducts
from app.modules.store.app.use_cases_impl.pricing_admin import SimulatePrices
from app.modules.store.app.use_cases_impl.quote import price_service
from app.modules.store.domain.eligibility import age_in_months, ineligibility
from app.modules.store.domain.models import Addon, Category, Product, Species
from app.modules.catalog.domain.breeds_data import BREEDS_CATALOG
from app.modules.store.domain.pricing import FALLBACK_CATEGORY, category_for_coat

_COAT = {b["id"]: b.get("coat_type") for g in BREEDS_CATALOG for b in g["breeds"]}


def price_category(breed_id, breed_name=None):
    """Misma regla que PostgresStoreRepository.price_category_for, con el catálogo semilla."""
    return category_for_coat(_COAT.get((breed_id or "").strip().lower()))

CATEGORY = uuid4()
CLASICO = uuid4()
SECO = uuid4()
DESLANADO = uuid4()
CEPILLO = uuid4()
TODAY = date.today()


def run(coro):
    return asyncio.run(coro)


def _months_ago(months: int) -> date:
    y, m = divmod(TODAY.year * 12 + TODAY.month - 1 - months, 12)
    return date(y, m + 1, min(TODAY.day, 28))


# ─── Edad y requisitos ────────────────────────────────────────────────────────


def test_age_in_months():
    assert age_in_months(None) is None
    assert age_in_months(date(2026, 6, 14), today=date(2026, 10, 14)) == 4
    assert age_in_months(date(2026, 6, 15), today=date(2026, 10, 14)) == 3
    assert age_in_months(date(2027, 1, 1), today=date(2026, 10, 14)) == 0


SECO_P = Product(id=SECO, category_id=CATEGORY, name="Express sin agua", species=Species.dog,
                 allowed_breeds=None, is_active=True, max_weight_kg=10, max_age_months=4)


@pytest.mark.parametrize(
    "weight, birth, code",
    [
        (8, _months_ago(3), None),
        (10, _months_ago(4), None),
        (10.5, _months_ago(3), "PET_TOO_HEAVY"),
        (8, _months_ago(5), "PET_TOO_OLD"),
        (8, None, "PET_AGE_UNKNOWN"),
    ],
)
def test_ineligibility(weight, birth, code):
    reason = ineligibility(SECO_P, weight=weight, birth_date=birth)
    assert (reason[0] if reason else None) == code


def test_product_without_limits_is_always_eligible():
    p = Product(id=CLASICO, category_id=CATEGORY, name="Fresco y Limpio", species=Species.dog,
                allowed_breeds=None, is_active=True)
    assert ineligibility(p, weight=60, birth_date=None) is None


# ─── Repositorios falsos ──────────────────────────────────────────────────────


class FakeRepo:
    """Precio por (target, categoría) con respaldo a "mestizo", como el repo real."""

    def __init__(self):
        self.products = {
            CLASICO: Product(id=CLASICO, category_id=CATEGORY, name="Fresco y Limpio", species=Species.dog,
                             allowed_breeds=None, is_active=True),
            SECO: SECO_P,
        }
        self.addons = {
            DESLANADO: Addon(id=DESLANADO, product_id=CLASICO, name="Deslanado intensivo", species=Species.dog,
                             allowed_breeds=None, is_active=True),
            CEPILLO: Addon(id=CEPILLO, product_id=CLASICO, name="Cepillo dental", species=Species.dog,
                           allowed_breeds=None, is_active=True),
        }
        self.rules = {
            (CLASICO, "double_short"): 129.0, (CLASICO, "mestizo"): 119.0,
            (SECO, "mestizo"): 75.0, (SECO, "simple_medium_long"): 75.0,
            (DESLANADO, "double_short"): 50.0,          # solo doble manto, sin fila mestizo
            (CEPILLO, "mestizo"): 15.0,
        }

    async def get_category_by_slug(self, slug):
        return Category(id=CATEGORY, name="PAKU Spa", slug=slug, species=None, is_active=True)

    async def list_products(self, *, category_id, species=None):
        return list(self.products.values())

    async def price_category_for(self, breed_id):
        return price_category(breed_id)

    async def get_product(self, product_id):
        return self.products.get(product_id)

    async def get_addon(self, addon_id):
        return self.addons.get(addon_id)

    async def list_addons(self, *, product_id):
        return [a for a in self.addons.values() if a.product_id == product_id]

    async def price_detail_for(self, *, target_id, target_type, species, breed_category, weight):
        if (target_id, breed_category) in self.rules:
            return self.rules[(target_id, breed_category)], breed_category
        if (target_id, "mestizo") in self.rules:
            return self.rules[(target_id, "mestizo")], "mestizo"
        return None, None

    async def price_for(self, **kw):
        return (await self.price_detail_for(**kw))[0]


class FakePets:
    def __init__(self, pet):
        self.pet = pet

    async def get_by_id(self, pet_id):
        return self.pet


def _pet(breed_id, weight, birth=None):
    return SimpleNamespace(id=uuid4(), owner_id=uuid4(), species=Species.dog, breed_id=breed_id,
                           breed_name=None, weight_kg=weight, birth_date=birth)


# ─── Cotización ───────────────────────────────────────────────────────────────


def test_quote_enforces_requirements_only_when_asked():
    old_heavy = _pet("shih_tzu", 12, _months_ago(24))
    with pytest.raises(HTTPException) as exc:
        run(price_service(FakeRepo(), pet=old_heavy, product_id=SECO, check_requirements=True))
    assert exc.value.status_code == 422 and exc.value.detail["code"] == "PET_TOO_HEAVY"
    # Recálculo por peso medido (feature 0003): no aplica requisitos
    assert run(price_service(FakeRepo(), pet=old_heavy, product_id=SECO)).product.price == 75.0


def test_quote_puppy_ok():
    puppy = _pet("shih_tzu", 6, _months_ago(3))
    result = run(price_service(FakeRepo(), pet=puppy, product_id=SECO, check_requirements=True))
    assert result.product.price == 75.0


# ─── Listados para la mascota ─────────────────────────────────────────────────


def test_list_products_hides_ineligible_service():
    adult = _pet("labrador", 30, _months_ago(36))
    items = run(ListProducts(repo=FakeRepo(), pets_repo=FakePets(adult)).execute(
        category_slug="spa", pet_id=adult.id))
    assert [i.product.name for i in items] == ["Fresco y Limpio"]

    puppy = _pet("shih_tzu", 6, _months_ago(3))
    items = run(ListProducts(repo=FakeRepo(), pets_repo=FakePets(puppy)).execute(
        category_slug="spa", pet_id=puppy.id))
    assert {i.product.name for i in items} == {"Fresco y Limpio", "Express sin agua"}


def test_list_products_without_pet_shows_all():
    items = run(ListProducts(repo=FakeRepo(), pets_repo=FakePets(None)).execute(category_slug="spa"))
    assert len(items) == 2


def test_product_detail_hides_addons_without_price():
    lab = _pet("labrador", 30)
    _, addons = run(GetProduct(repo=FakeRepo(), pets_repo=FakePets(lab)).execute(
        product_id=CLASICO, pet_id=lab.id))
    assert {a.addon.name for a in addons} == {"Deslanado intensivo", "Cepillo dental"}

    shih = _pet("shih_tzu", 6)
    _, addons = run(GetProduct(repo=FakeRepo(), pets_repo=FakePets(shih)).execute(
        product_id=CLASICO, pet_id=shih.id))
    assert [a.addon.name for a in addons] == ["Cepillo dental"]  # deslanado no aplica


def test_simulation_skips_service_over_max_weight():
    result = run(SimulatePrices(repo=FakeRepo()).execute(
        category_id=CATEGORY, species=Species.dog, weight=12, breed_id="shih_tzu"))
    assert [p.name for p in result.products] == ["Fresco y Limpio"]


# ─── Razas según el documento de precios ──────────────────────────────────────


def test_breeds_from_pricing_document():
    assert price_category("pug") == "double_short"           # S4
    assert price_category("pekines") == "double_long"        # S5
    assert price_category("lagotto_romagnolo") == "curly_no_undercoat"
    assert price_category("perro_agua_portugues") == "curly_no_undercoat"
    assert price_category("aussiedoodle") == "mixed_curly_undercoat"
