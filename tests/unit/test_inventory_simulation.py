"""Feature 0019: simulador de un servicio (receta por pelaje y peso, precio, mano de obra, stock). Repositorios falsos."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.inventory.app.simulation import SimulateService
from app.modules.inventory.domain.inventory import Recipe, RecipeCell, RecipeLine, Supply
from app.modules.store.domain.models import Addon, Product, Species

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)


def _supply(sku, name, unit, purchase_cost, content, min_stock=0):
    return Supply(id=uuid4(), sku=sku, name=name, category="cosmetic", purchase_unit="frasco", purchase_content=content,
                  consumption_unit=unit, purchase_cost=purchase_cost, min_stock=min_stock, tracks_lot=False,
                  tracks_expiry=False, is_active=True, created_at=NOW, updated_at=NOW)


SHAMPOO = _supply("INS-001", "Shampoo", "ml", 100, 1000, min_stock=500)    # S/ 0.10 por ml
PERFUME = _supply("INS-002", "Perfume", "ml", 60, 200)                     # S/ 0.30 por ml
TOALLA = _supply("INS-003", "Toalla desechable", "unidad", 50, 100)        # S/ 0.50 c/u
SUPPLIES = {s.id: s for s in (SHAMPOO, PERFUME, TOALLA)}

BANO = Product(id=uuid4(), category_id=uuid4(), name="Baño Clásico", species=Species.dog, allowed_breeds=None,
               is_active=True, max_weight_kg=40)
OTRO = Product(id=uuid4(), category_id=uuid4(), name="Spa", species=Species.dog, allowed_breeds=None, is_active=True)
PERF = Addon(id=uuid4(), product_id=BANO.id, name="Perfume premium", species=Species.dog, allowed_breeds=None,
             is_active=True)
CORTE = Addon(id=uuid4(), product_id=BANO.id, name="Corte de uñas", species=Species.dog, allowed_breeds=None,
              is_active=True)
AJENO = Addon(id=uuid4(), product_id=OTRO.id, name="Hidratación", species=Species.dog, allowed_breeds=None,
              is_active=True)


def _cell(category, wmin, wmax, minutes, *lines):
    return RecipeCell(breed_category=category, weight_min=wmin, weight_max=wmax, labor_minutes=minutes,
                      lines=[RecipeLine(s.id, q) for s, q in lines], id=uuid4())


RECIPES = {
    BANO.id: Recipe(id=uuid4(), target_type="product", target_id=BANO.id, version=2, is_current=True, created_at=NOW,
                    cells=[_cell("corto", 0, 5, 40, (SHAMPOO, 50), (TOALLA, 2)),
                           _cell("corto", 5.01, 15, 60, (SHAMPOO, 120), (TOALLA, 3)),
                           _cell("mestizo", 5.01, 15, 70, (SHAMPOO, 150), (TOALLA, 3))]),
    PERF.id: Recipe(id=uuid4(), target_type="addon", target_id=PERF.id, version=1, is_current=True, created_at=NOW,
                    cells=[_cell("mestizo", 0, None, 5, (PERFUME, 10))]),
    # CORTE no tiene receta
}
PRICES = {(BANO.id, "corto", "5.01-15"): 70.0, (BANO.id, "mestizo", "5.01-15"): 80.0,
          (PERF.id, "mestizo", "0-"): 15.0}


class StoreRepo:
    async def get_product(self, pid):
        return {BANO.id: BANO, OTRO.id: OTRO}.get(pid)

    async def get_addon(self, aid):
        return {PERF.id: PERF, CORTE.id: CORTE, AJENO.id: AJENO}.get(aid)

    async def price_category_for(self, breed_id):
        return {"shih_tzu": "corto"}.get(breed_id, "mestizo")

    async def price_for(self, *, target_id, target_type, species, breed_category, weight):
        for (tid, cat, tier), price in PRICES.items():
            low, high = tier.split("-")
            if tid == target_id and float(low) <= weight and (not high or weight <= float(high)):
                if cat == breed_category:
                    return price
        for (tid, cat, tier), price in PRICES.items():  # respaldo mestizo, como la tabla real
            low, high = tier.split("-")
            if tid == target_id and cat == "mestizo" and float(low) <= weight and (not high or weight <= float(high)):
                return price
        return None


class InventoryRepo:
    async def current_recipes_for(self, ids):
        return {i: RECIPES[i] for i in ids if i in RECIPES}

    async def get_supplies(self, ids):
        return {i: SUPPLIES[i] for i in ids if i in SUPPLIES}

    async def stock_by_supply(self, until=None):
        return {SHAMPOO.id: 1000.0, TOALLA.id: 10.0}  # perfume sin stock


class BreedsRepo:
    async def get(self, breed_id):
        return SimpleNamespace(id=breed_id, name="Shih Tzu") if breed_id == "shih_tzu" else None


def _simulate(**kw):
    args = dict(product_id=BANO.id, addon_ids=[PERF.id], breed_id="shih_tzu", weight_kg=8.0, rates=(30.0, "reference"))
    args.update(kw)
    service = SimulateService(repo=InventoryRepo(), store_repo=StoreRepo(), breeds_repo=BreedsRepo())
    return asyncio.run(service.execute(**args))


def test_simulation_costs_and_margin():
    sim = _simulate()
    assert (sim.breed_category, sim.breed_name, sim.weight_code, sim.category_label) == (
        "corto", "Shih Tzu", "W02", sim.category_label)
    base, perfume = sim.items
    # Base: celda corto 5.01–15 → 120 ml shampoo (S/ 12) + 3 toallas (S/ 1.50), 60 min, precio S/ 70
    assert (base.recipe_version, base.category_used, base.labor_minutes, base.price) == ("R2", "corto", 60, 70.0)
    assert round(base.supplies_cost, 2) == 13.5
    # Perfume: solo fila mestizo → respaldo; 10 ml × 0.30 = S/ 3, 5 min, precio S/ 15
    assert (perfume.category_used, perfume.labor_minutes, perfume.price, round(perfume.supplies_cost, 2)) == (
        "mestizo", 5, 15.0, 3.0)
    # 65 min × S/ 30 / h = 32.50; costo 16.50 + 32.50 = 49; margen 85 − 49 = 36 (42.4 %)
    assert (sim.price, sim.supplies_cost, sim.labor_minutes, sim.labor_cost, sim.total_cost) == (
        85.0, 16.5, 65, 32.5, 49.0)
    assert (sim.margin, sim.margin_pct) == (36.0, 42.4)
    assert sim.warnings == []


def test_simulation_supplies_against_stock():
    sim = _simulate()
    by_sku = {s.supply.sku: s for s in sim.supplies}
    assert [s.supply.sku for s in sim.supplies] == ["INS-001", "INS-002", "INS-003"]  # más caro primero
    assert (by_sku["INS-001"].quantity, by_sku["INS-001"].services_with_stock, by_sku["INS-001"].stock_status) == (
        120, 8, "ok")
    assert by_sku["INS-003"].services_with_stock == 3          # 10 toallas / 3
    assert (by_sku["INS-002"].stock, by_sku["INS-002"].services_with_stock, by_sku["INS-002"].stock_status) == (
        0.0, 0, "out")


def test_simulation_without_breed_uses_mestizo_and_reports_gaps():
    sim = _simulate(breed_id=None, addon_ids=[PERF.id, CORTE.id, PERF.id], rates=(None, "reference"))
    assert sim.breed_category == "mestizo"
    assert [i.target.name for i in sim.items] == ["Baño Clásico", "Perfume premium", "Corte de uñas"]  # sin repetir
    assert sim.items[0].labor_minutes == 70 and sim.items[0].price == 80.0
    corte = sim.items[2]
    assert (corte.recipe_version, corte.price, corte.lines) == (None, None, [])
    assert sim.price is None and sim.labor_cost is None and sim.margin is None
    assert sim.warnings == [
        "«Corte de uñas» no tiene receta para este pelaje y peso: no suma insumos ni minutos.",
        "«Corte de uñas» no tiene precio para este pelaje y peso.",
        "No hay costo por hora de groomer registrado: falta la mano de obra.",
    ]


def test_simulation_weight_outside_service_limit_warns():
    sim = _simulate(weight_kg=45, addon_ids=[])
    assert sim.items[0].recipe_version is None   # no hay celda de más de 15 kg
    assert sim.warnings[0] == "El servicio admite hasta 40 kg; en la app no se podría comprar."


@pytest.mark.parametrize("kw,code", [
    (dict(weight_kg=0), "WEIGHT_INVALID"),
    (dict(weight_kg=200), "WEIGHT_INVALID"),
    (dict(product_id=uuid4()), "PRODUCT_NOT_FOUND"),
    (dict(addon_ids=[uuid4()]), "ADDON_NOT_FOUND"),
    (dict(addon_ids=[AJENO.id]), "ADDON_NOT_IN_SERVICE"),
    (dict(breed_id="no_existe"), "BREED_NOT_FOUND"),
])
def test_simulation_errors(kw, code):
    with pytest.raises(HTTPException) as exc:
        _simulate(**kw)
    assert exc.value.detail["code"] == code


def test_simulation_response():
    from app.modules.inventory.api.router import _simulation_out

    out = _simulation_out(_simulate())
    assert (out.product_name, out.breed_category, out.price, out.margin_pct) == ("Baño Clásico", "corto", 85.0, 42.4)
    assert [(s.sku, s.cost, s.cost_share_pct) for s in out.supplies] == [
        ("INS-001", 12.0, 72.7), ("INS-002", 3.0, 18.2), ("INS-003", 1.5, 9.1)]
    assert out.max_services_with_stock == 0   # el perfume ya no tiene stock
    assert [i.target_type for i in out.items] == ["product", "addon"]
