"""Feature 0009-inventario: stock por movimientos, recetas como la tabla de precios (pelaje × peso) con
minutos de groomer, consumo al terminar la orden y costo por orden (insumos + mano de obra)."""
import asyncio
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.timezone import today_lima
from app.modules.groomer_costs.app.use_cases import LaborRates
from app.modules.inventory.app import order_hook
from app.modules.inventory.app.use_cases import (
    CreateSupply,
    GetInventorySummary,
    GetOrderCost,
    ListSupplies,
    OrderConsumption,
    RegisterMovement,
    SaveRecipe,
    UpdateSupply,
    VoidMovement,
    EditMovement,
    order_real_minutes,
)
from app.modules.inventory.domain.inventory import (
    MovementEdit,
    price_without_igv,
    weighted_unit_cost,
    ConsumptionTarget,
    Movement,
    Recipe,
    RecipeCell,
    RecipeLine,
    Supply,
    find_cell,
    next_code,
    plan_consumption,
    signed_quantity,
    stock_status,
    weight_code_for,
)
from app.modules.inventory.infra.models import RecipeCellModel, RecipeLineModel, RecipeModel, SupplyModel
from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
from app.modules.orders.domain.order import Order, OrderStatus, PaymentStatus
from app.modules.pets.domain.pet import Pet, Species

NOW = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
PRODUCT_ID = uuid4()
ADDON_ID = uuid4()
ADMIN = uuid4()
GROOMER = uuid4()
# Tramos de la tabla de precios (GET /admin/store/price-config)
T1, T2, T3 = (0, 5), (5.01, 15), (15.01, 25)


def _run(coro):
    return asyncio.run(coro)


def _detail(exc: pytest.ExceptionInfo) -> dict:
    return exc.value.detail


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


# ─── Dobles ──────────────────────────────────────────────────────────────────

class _Repo:
    """Repositorio de inventario en memoria."""

    def __init__(self):
        self.supplies: dict[UUID, Supply] = {}
        self.movements: list[Movement] = []
        self.recipes: dict[UUID, Recipe] = {}
        self.edits: list[MovementEdit] = []

    async def list_supplies(self, *, include_inactive=True):
        return [s for s in sorted(self.supplies.values(), key=lambda s: s.sku) if include_inactive or s.is_active]

    async def get_supply(self, supply_id):
        return self.supplies.get(supply_id)

    async def get_supplies(self, ids):
        return {i: self.supplies[i] for i in ids if i in self.supplies}

    async def list_skus(self):
        return [s.sku for s in self.supplies.values()]

    async def create_supply(self, *, sku, fields):
        if sku in await self.list_skus():
            raise ValueError("sku_taken")
        s = Supply(id=uuid4(), sku=sku, created_at=NOW, updated_at=NOW, is_active=True,
                   **{"tracks_lot": False, "tracks_expiry": False, "min_stock": 0,
                      **{k: _num(v) for k, v in fields.items()}})
        self.supplies[s.id] = s
        return s

    async def update_supply(self, supply_id, patch):
        if supply_id not in self.supplies:
            raise ValueError("supply_not_found")
        self.supplies[supply_id] = replace(self.supplies[supply_id], **{k: _num(v) for k, v in patch.items()})
        return self.supplies[supply_id]

    async def stock_by_supply(self):
        out = {}
        for m in self.movements:
            if m.is_voided:
                continue
            out[m.supply_id] = out.get(m.supply_id, 0.0) + m.quantity
        return out

    async def add_movements(self, rows, *, commit=True):
        created = []
        for row in rows:
            m = Movement(id=uuid4(), seq=len(self.movements) + 1, created_at=NOW, **{k: _num(v) for k, v in row.items()})
            self.movements.append(m)
            created.append(m)
        return created

    async def list_movements(self, *, type=None, supply_id=None, order_id=None, date_from=None, date_to=None,
                             include_voided=False, limit=500):
        rows = [m for m in self.movements if (include_voided or not m.is_voided) and (not type or m.type == type) and (not supply_id or m.supply_id == supply_id)
                and (not order_id or m.order_id == order_id)]
        return sorted(rows, key=lambda m: (m.occurred_on, m.seq), reverse=True)[:limit]

    async def get_movement(self, movement_id):
        return next((m for m in self.movements if m.id == movement_id), None)

    async def void_movement(self, movement_id, *, actor_id, reason):
        for i, m in enumerate(self.movements):
            if m.id == movement_id and not m.is_voided:
                self.movements[i] = replace(m, voided_at=NOW, voided_by=actor_id, void_reason=reason)
                return True
        return False

    async def edit_movement(self, movement_id, values, *, actor_id, reason, changes):
        for i, m in enumerate(self.movements):
            if m.id == movement_id and not m.is_voided:
                self.movements[i] = replace(m, edited_at=NOW, edited_by=actor_id, **{k: _num(v) for k, v in values.items()})
                self.edits.append(MovementEdit(id=uuid4(), movement_id=movement_id, edited_at=NOW, edited_by=actor_id,
                                               reason=reason, changes=changes))
                return True
        return False

    async def has_order_consumption(self, order_id):
        return any(m.order_id == order_id and m.type == "consumption" for m in self.movements)

    async def consumption_totals(self, *, date_from, date_to):
        rows = [m for m in self.movements if m.type == "consumption"
                and (not date_from or m.occurred_on >= date_from) and (not date_to or m.occurred_on <= date_to)]
        return sum(-m.quantity * m.unit_cost for m in rows), len({m.order_id for m in rows if m.order_id})

    async def current_recipes_for(self, target_ids):
        return {r.target_id: r for r in self.recipes.values() if r.is_current and r.target_id in target_ids}

    async def get_recipes(self, ids):
        return {i: self.recipes[i] for i in ids if i in self.recipes}

    async def save_recipe_version(self, *, target_type, target_id, version, cells, created_by, replaces=None):
        if replaces is not None:
            self.recipes[replaces] = replace(self.recipes[replaces], is_current=False)
        r = Recipe(id=uuid4(), target_type=target_type, target_id=target_id, version=version, is_current=True,
                   cells=[replace(c, id=uuid4()) for c in cells], created_at=NOW, created_by=created_by)
        self.recipes[r.id] = r
        return r


class _Store:
    def __init__(self, category="double_long"):
        self.category = category

    async def get_product(self, product_id):
        return object() if product_id == PRODUCT_ID else None

    async def get_addon(self, addon_id):
        return object() if addon_id == ADDON_ID else None

    async def price_category_for(self, breed_id):
        return self.category


class _Pets:
    def __init__(self, pet):
        self.pet = pet

    async def get_by_id(self, pet_id, include_deleted=False):
        return self.pet if self.pet and pet_id == self.pet.id else None


def _pet() -> Pet:
    return Pet(id=uuid4(), owner_id=uuid4(), name="Rocky", species=Species.dog, breed_id="golden_retriever",
               breed_name="Golden", sex=None, birth_date=None, notes=None, created_at=NOW, weight_kg=18.0)


def _order(pet: Pet, *, declared=12.0, measured=18.0, addon=True, **fields) -> Order:
    items = [{"kind": "service_base", "ref_id": str(PRODUCT_ID), "name": "Spa Deluxe", "qty": 1, "unit_price": 135,
              "meta": {"pet_id": str(pet.id), "pet_weight_kg": declared}}]
    if addon:
        items.append({"kind": "service_addon", "ref_id": str(ADDON_ID), "name": "Deslanado intensivo", "qty": 1,
                      "unit_price": 25, "meta": {"pet_id": str(pet.id)}})
    order = Order.new(user_id=pet.owner_id, items_snapshot=items, total_snapshot=160.0)
    return replace(order, **{"status": OrderStatus.done, "payment_status": PaymentStatus.paid, "completed_at": NOW,
                             "measured_weight_kg": measured, "groomer_id": GROOMER, **fields})


def _supply(repo: _Repo, name="Shampoo", content=3785, cost=185, **fields) -> Supply:
    row = _run(CreateSupply(repo=repo).execute(fields={
        "name": name, "category": "cosmetic", "purchase_unit": "Galón", "purchase_content": content,
        "consumption_unit": "ml", "purchase_cost": cost, **fields,
    }))
    return row.supply


def _cell(category, tier, minutes=0, lines=()):
    return {"breed_category": category, "weight_min": tier[0], "weight_max": tier[1], "labor_minutes": minutes,
            "lines": [{"supply_id": s.id, "quantity": q} for s, q in lines]}


def _save(repo, cells, *, target_type="product", target_id=PRODUCT_ID):
    return _run(SaveRecipe(repo=repo, store_repo=_Store()).execute(
        target_type=target_type, target_id=target_id, cells=cells, actor_id=ADMIN))


def _rates(rate=15.0, by_groomer=True):
    profile = SimpleNamespace(cost_per_service_hour=rate)
    return LaborRates(day=date(2026, 10, 20), by_groomer={GROOMER: profile} if by_groomer else {}, reference=12.0)


# ─── Reglas puras ────────────────────────────────────────────────────────────

def test_weight_codes_follow_price_tiers():
    assert weight_code_for(None) is None
    assert weight_code_for(5) == "W01"
    assert weight_code_for(5.005) == "W02"
    assert weight_code_for(80) == "W06"


def test_stock_status_and_signs():
    assert stock_status(0, 10) == "out"
    assert stock_status(5, 10) == "low"
    assert stock_status(10, 10) == "ok"
    assert signed_quantity("purchase", 5) == 5
    assert signed_quantity("waste", 5) == -5
    assert signed_quantity("adjustment", 5, "in") == 5
    assert signed_quantity("adjustment", 5, "out") == -5


def test_next_code():
    assert next_code([], "INS-") == "INS-001"
    assert next_code(["INS-001", "INS-007"], "INS-") == "INS-008"


def _rc(category, tier, minutes=0):
    return RecipeCell(breed_category=category, weight_min=tier[0], weight_max=tier[1], labor_minutes=minutes, lines=[])


def test_find_cell_uses_the_price_rule():
    cells = [_rc("double_long", T3, 90), _rc("mestizo", T2, 60), _rc("mestizo", T3, 80)]
    assert find_cell(cells, breed_category="double_long", weight=18)[1] == "double_long"
    # Falta la celda del pelaje en ese peso: usa la fila "mestizo", como el precio
    cell, used = find_cell(cells, breed_category="double_long", weight=10)
    assert (used, cell.labor_minutes) == ("mestizo", 60)
    # 5,004 kg se redondea a 5,01: tramo 2 (igual que price_detail_for)
    assert find_cell(cells, breed_category="mestizo", weight=5.004)[0].weight_min == 5.01
    assert find_cell(cells, breed_category="double_long", weight=3) == (None, None)


def test_plan_consumption_marks_missing():
    recipe = Recipe(id=uuid4(), target_type="addon", target_id=ADDON_ID, version=1, is_current=True,
                    cells=[_rc("double_short", T3, 20), _rc("double_long", T3, 20)], created_at=NOW)
    targets = [ConsumptionTarget("product", str(PRODUCT_ID), "Spa Deluxe"),
               ConsumptionTarget("addon", str(ADDON_ID), "Deslanado")]
    plan = plan_consumption(targets, {str(ADDON_ID): recipe}, breed_category="double_long", weight_kg=18)
    assert [pc.target.name for pc in plan.cells] == ["Deslanado"] and plan.labor_minutes == 20
    assert [t.name for t in plan.missing] == ["Spa Deluxe"]
    # Sin peso no hay celda
    assert len(plan_consumption(targets, {str(ADDON_ID): recipe}, breed_category="double_long", weight_kg=None).missing) == 2


# ─── Insumos y movimientos ───────────────────────────────────────────────────

def test_create_supply_assigns_code_and_unit_cost():
    repo = _Repo()
    first, second = _supply(repo), _supply(repo, name="Guantes", content=100, cost=32)
    assert (first.sku, second.sku) == ("INS-001", "INS-002")
    assert round(first.unit_cost, 4) == round(185 / 3785, 4)


def test_movements_set_stock_and_keep_cost_of_the_moment():
    repo = _Repo()
    shampoo = _supply(repo, min_stock=1000)
    register = RegisterMovement(repo=repo)
    _run(register.execute(type="purchase", supply_id=shampoo.id, quantity=3785, purchase_total=185, reason="F001-1", actor_id=ADMIN))
    _run(register.execute(type="waste", supply_id=shampoo.id, quantity=900, reason="Derrame", actor_id=ADMIN))
    _run(register.execute(type="adjustment", direction="out", supply_id=shampoo.id, quantity=2100, reason="Conteo", actor_id=ADMIN))
    _run(register.execute(type="adjustment", direction="in", supply_id=shampoo.id, quantity=100, reason="Conteo", actor_id=ADMIN))
    [row] = _run(ListSupplies(repo=repo).execute())
    assert (row.stock, row.status) == (885, "low")
    _run(UpdateSupply(repo=repo).execute(shampoo.id, fields={"purchase_cost": 370}))
    assert repo.movements[0].unit_cost == pytest.approx(185 / 3785, rel=1e-5)


def test_movement_rules():
    repo = _Repo()
    shampoo = _supply(repo)
    register = RegisterMovement(repo=repo)
    cases = [
        ({"type": "adjustment", "quantity": 5, "reason": "x"}, "MOVEMENT_DIRECTION_REQUIRED"),
        ({"type": "purchase", "quantity": 5, "purchase_total": 1, "reason": "  "}, "MOVEMENT_REASON_REQUIRED"),
        ({"type": "purchase", "quantity": 5, "purchase_total": 1, "reason": "x",
          "occurred_on": today_lima() + timedelta(days=1)}, "MOVEMENT_DATE_IN_FUTURE"),
        ({"type": "purchase", "quantity": 5, "purchase_total": 1, "reason": "x", "location": "Otra van"},
         "LOCATION_INVALID"),
        ({"type": "purchase", "quantity": 5, "reason": "x"}, "MOVEMENT_PRICE_REQUIRED"),
        ({"type": "waste", "quantity": 5, "purchase_total": 1, "reason": "x"}, "MOVEMENT_PRICE_NOT_ALLOWED"),
        ({"type": "purchase", "quantity": 0, "purchase_total": 1, "reason": "x"}, "MOVEMENT_QUANTITY_INVALID"),
    ]
    for kwargs, code in cases:
        with pytest.raises(HTTPException) as exc:
            _run(register.execute(supply_id=shampoo.id, actor_id=ADMIN, **kwargs))
        assert _detail(exc)["code"] == code


def test_supply_brand_description_suppliers_and_liters():
    repo = _Repo()
    shampoo = _supply(repo, consumption_unit="L", content=3.785, brand="  Iv San Bernard ", description="",
                      suppliers=[{"name": " Distribuidora Pet ", "product_code": " SH-500 ", "phone": "", "ruc": "20123456789",
                                  "bank_account": "BCP 191-1234567-0-12"}])
    assert (shampoo.consumption_unit, shampoo.brand, shampoo.description) == ("L", "Iv San Bernard", None)
    assert shampoo.suppliers == [{"name": "Distribuidora Pet", "product_code": "SH-500", "phone": None, "address": None,
                                  "bank_account": "BCP 191-1234567-0-12", "ruc": "20123456789"}]
    assert round(shampoo.unit_cost, 2) == round(185 / 3.785, 2)
    updated = _run(UpdateSupply(repo=repo).execute(shampoo.id, fields={"suppliers": [], "brand": None}))
    assert (updated.supply.suppliers, updated.supply.brand) == ([], None)
    for suppliers, code in (([{"name": " "}], "SUPPLIER_NAME_REQUIRED"),
                            ([{"name": "A"}, {"name": "B", "ruc": "2012345"}], "SUPPLIER_RUC_INVALID")):
        with pytest.raises(HTTPException) as exc:
            _run(UpdateSupply(repo=repo).execute(shampoo.id, fields={"suppliers": suppliers}))
        assert _detail(exc)["code"] == code
    assert _detail(exc)["index"] == 1


def test_purchase_price_updates_weighted_average_cost():
    repo = _Repo()
    shampoo = _supply(repo)                       # galón de 3785 ml a S/ 185
    register = RegisterMovement(repo=repo)
    initial = _run(register.execute(type="initial_stock", supply_id=shampoo.id, quantity=3785, reason="Conteo",
                                    actor_id=ADMIN))
    assert initial.unit_cost == pytest.approx(185 / 3785, rel=1e-5)
    assert repo.supplies[shampoo.id].purchase_cost == 185  # sin precio: no cambia el costo
    # Se compra la cantidad real (2 galones = 7570 ml) por el total pagado (S/ 430 = S/ 215 por galón)
    bought = _run(register.execute(type="purchase", supply_id=shampoo.id, quantity=7570, purchase_total=430,
                                   reason="F001-2", actor_id=ADMIN))
    assert (bought.quantity, bought.purchase_total) == (7570, 430)
    assert bought.unit_cost == pytest.approx(215 / 3785, rel=1e-5)          # la compra queda a su precio
    assert repo.supplies[shampoo.id].purchase_cost == pytest.approx(205, abs=0.01)  # (1×185 + 2×215) ÷ 3
    # Después la merma sale al costo promedio
    waste = _run(register.execute(type="waste", supply_id=shampoo.id, quantity=100, reason="Derrame", actor_id=ADMIN))
    assert waste.unit_cost == pytest.approx(205 / 3785, rel=1e-4)


def test_price_without_igv():
    assert round(price_without_igv(75, 18), 2) == 63.56
    assert price_without_igv(75, 0) == 75


def test_recipe_cell_margin_is_net_of_igv():
    """Celda: costo = insumos + minutos × tarifa; margen = precio sin IGV − costo."""
    from app.modules.inventory.api.router import _recipe_out

    repo = _Repo()
    shampoo = _supply(repo, content=1000, cost=50)             # S/ 0,05 por ml
    cell = RecipeCell(breed_category="corto", weight_min=0, weight_max=5, labor_minutes=30,
                      lines=[RecipeLine(shampoo.id, 100)])
    recipe = Recipe(id=uuid4(), target_type="product", target_id=PRODUCT_ID, version=1, is_current=True,
                    cells=[cell], created_at=NOW)

    class _Prices:
        async def list_price_rules(self, *, target_id):
            return [SimpleNamespace(is_active=True, breed_category="corto", weight_min=0, weight_max=5, price=75)]

    out = _run(_recipe_out(recipe, repo, _Prices(), 12.0, "Baño", 18))
    [c] = out.cells
    assert (c.supplies_cost, c.labor_cost, c.total_cost) == (5.0, 6.0, 11.0)
    assert (c.price, c.price_without_igv, c.margin) == (75, 63.56, 52.56)
    assert out.igv_percent == 18


def test_weighted_cost_ignores_negative_stock():
    assert weighted_unit_cost(-50, 1.0, 100, 2.0) == 2.0
    assert weighted_unit_cost(100, 1.0, 100, 2.0) == 1.5


def test_purchase_in_real_quantity_with_total_paid():
    """Agua en recarga de 200 L: se compran 100 L por S/ 50 → S/ 0,50 por L, sin poner «0,5 recargas»."""
    repo = _Repo()
    water = _supply(repo, name="Agua", content=200, cost=120, consumption_unit="L")   # S/ 0,60 por L
    register = RegisterMovement(repo=repo)
    bought = _run(register.execute(type="purchase", supply_id=water.id, quantity=100, purchase_total=50,
                                   reason="B001-9", actor_id=ADMIN))
    assert (bought.quantity, bought.purchase_total, bought.unit_cost) == (100, 50, 0.5)
    assert repo.supplies[water.id].purchase_cost == 100.0   # sin stock previo: 0,50 × 200 L


def test_edit_movement_recalculates_stock_and_keeps_history():
    repo = _Repo()
    water = _supply(repo, name="Agua", content=200, cost=120, consumption_unit="L")
    other = _supply(repo, name="Shampoo")
    register, editor = RegisterMovement(repo=repo), EditMovement(repo=repo)
    bought = _run(register.execute(type="purchase", supply_id=water.id, quantity=100, purchase_total=50,
                                   reason="B001-9", actor_id=ADMIN))
    cost_after_purchase = repo.supplies[water.id].purchase_cost
    edited = _run(editor.execute(bought.id, changes={"quantity": 80, "reason": "B001-10"}, edit_reason=" Error de tipeo ",
                                 actor_id=ADMIN))
    assert (edited.quantity, edited.unit_cost, edited.reason) == (80, 0.625, "B001-10")   # 50 ÷ 80
    assert (edited.edited_by, edited.can_edit) == (ADMIN, True)
    [row_water, _] = _run(ListSupplies(repo=repo).execute())
    assert row_water.stock == 80
    assert repo.supplies[water.id].purchase_cost == cost_after_purchase  # el promedio no se recalcula
    [edit] = repo.edits
    assert edit.reason == "Error de tipeo"
    assert edit.changes == {"quantity": {"before": 100, "after": 80}, "unit_cost": {"before": 0.5, "after": 0.625},
                            "reason": {"before": "B001-9", "after": "B001-10"}}
    # Mover a otro insumo
    moved = _run(editor.execute(bought.id, changes={"supply_id": other.id}, edit_reason="Insumo equivocado", actor_id=ADMIN))
    assert moved.supply_id == other.id and moved.unit_cost == 0.625
    # Ajuste: cambiar la dirección invierte el signo
    adj = _run(register.execute(type="adjustment", direction="out", supply_id=water.id, quantity=5, reason="Conteo",
                                actor_id=ADMIN))
    flipped = _run(editor.execute(adj.id, changes={"direction": "in"}, edit_reason="Era entrada", actor_id=ADMIN))
    assert flipped.quantity == 5


def test_edit_movement_rules():
    repo = _Repo()
    water = _supply(repo, name="Agua", content=200, cost=120, consumption_unit="L")
    register, editor = RegisterMovement(repo=repo), EditMovement(repo=repo)
    bought = _run(register.execute(type="purchase", supply_id=water.id, quantity=100, purchase_total=50,
                                   reason="B001-9", actor_id=ADMIN))
    waste = _run(register.execute(type="waste", supply_id=water.id, quantity=5, reason="Fuga", actor_id=ADMIN))
    [recipe_consumption] = _run(repo.add_movements([{
        "occurred_on": today_lima(), "type": "consumption", "supply_id": water.id, "quantity": Decimal("-10"),
        "unit_cost": Decimal("0.5"), "location": None, "cost_center": None, "reason": "Receta", "order_id": uuid4(),
        "recipe_id": uuid4(),
    }]))
    voided = _run(register.execute(type="waste", supply_id=water.id, quantity=1, reason="x", actor_id=ADMIN))
    _run(VoidMovement(repo=repo).execute(voided.id, reason="Duplicado", actor_id=ADMIN))
    cases = [
        (bought.id, {"quantity": 90}, " ", "EDIT_REASON_REQUIRED"),
        (uuid4(), {"quantity": 90}, "x", "MOVEMENT_NOT_FOUND"),
        (recipe_consumption.id, {"quantity": 9}, "x", "MOVEMENT_NOT_EDITABLE"),
        (voided.id, {"quantity": 2}, "x", "MOVEMENT_NOT_EDITABLE"),
        (bought.id, {"quantity": 100}, "x", "MOVEMENT_UNCHANGED"),
        (bought.id, {"purchase_total": None}, "x", "MOVEMENT_PRICE_REQUIRED"),
        (waste.id, {"purchase_total": 3}, "x", "MOVEMENT_PRICE_NOT_ALLOWED"),
        (bought.id, {"occurred_on": today_lima() + timedelta(days=1)}, "x", "MOVEMENT_DATE_IN_FUTURE"),
        (bought.id, {"supply_id": uuid4()}, "x", "SUPPLY_NOT_FOUND"),
    ]
    for movement_id, changes, reason, code in cases:
        with pytest.raises(HTTPException) as exc:
            _run(editor.execute(movement_id, changes=changes, edit_reason=reason, actor_id=ADMIN))
        assert _detail(exc)["code"] == code, code


def test_void_manual_movement_stops_counting():
    repo = _Repo()
    shampoo = _supply(repo)
    register = RegisterMovement(repo=repo)
    _run(register.execute(type="purchase", supply_id=shampoo.id, quantity=3785, purchase_total=185, reason="F001-1", actor_id=ADMIN))
    wrong = _run(register.execute(type="purchase", supply_id=shampoo.id, quantity=3785, purchase_total=185, reason="F001-1", actor_id=ADMIN))
    assert wrong.can_void
    voided = _run(VoidMovement(repo=repo).execute(wrong.id, reason=" Duplicado ", actor_id=ADMIN))
    assert (voided.is_voided, voided.can_void, voided.void_reason, voided.voided_by) == (True, False, "Duplicado", ADMIN)
    [row] = _run(ListSupplies(repo=repo).execute())
    assert row.stock == 3785
    assert len(_run(repo.list_movements())) == 1
    assert len(_run(repo.list_movements(include_voided=True))) == 2
    cases = [(wrong.id, "x", "MOVEMENT_ALREADY_VOIDED"), (uuid4(), "x", "MOVEMENT_NOT_FOUND"),
             (repo.movements[0].id, "  ", "VOID_REASON_REQUIRED")]
    for movement_id, reason, code in cases:
        with pytest.raises(HTTPException) as exc:
            _run(VoidMovement(repo=repo).execute(movement_id, reason=reason, actor_id=ADMIN))
        assert _detail(exc)["code"] == code


def test_order_consumption_cannot_be_voided():
    repo = _Repo()
    shampoo = _supply(repo)
    [consumption] = _run(repo.add_movements([{
        "occurred_on": today_lima(), "type": "consumption", "supply_id": shampoo.id, "quantity": Decimal("-25"),
        "unit_cost": Decimal("0.05"), "location": None, "cost_center": None, "reason": "Receta", "order_id": uuid4(),
        "recipe_id": uuid4(),
    }]))
    assert not consumption.can_void
    with pytest.raises(HTTPException) as exc:
        _run(VoidMovement(repo=repo).execute(consumption.id, reason="x", actor_id=ADMIN))
    assert _detail(exc)["code"] == "MOVEMENT_NOT_VOIDABLE"
    manual = _run(RegisterMovement(repo=repo).execute(type="consumption", supply_id=shampoo.id, quantity=10,
                                                      reason="Prueba", actor_id=ADMIN))
    assert manual.can_void  # un consumo manual sí se anula


def test_supply_and_void_repository_roundtrip_sqlite():
    """Marca, proveedores y anulación con el repositorio real."""
    from app.modules.iam.infra.models import UserModel
    from app.modules.inventory.infra.models import MovementEditModel, MovementModel

    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[
                UserModel.__table__, SupplyModel.__table__, MovementModel.__table__, MovementEditModel.__table__,
            ])
        session = async_sessionmaker(engine, expire_on_commit=False)()
        repo = PostgresInventoryRepository(session=session)
        supply = await repo.create_supply(sku="INS-001", fields={
            "name": "Shampoo", "brand": "Iv San Bernard", "category": "cosmetic", "purchase_unit": "Galón",
            "purchase_content": Decimal("3.785"), "consumption_unit": "L", "purchase_cost": Decimal("185"),
            "min_stock": Decimal("0"), "suppliers": [{"name": "Distribuidora Pet", "ruc": "20123456789"}],
        })
        assert (supply.brand, supply.suppliers[0]["name"]) == ("Iv San Bernard", "Distribuidora Pet")
        a, b = await repo.add_movements([
            {"seq": 1, "occurred_on": date(2026, 11, 1), "type": "purchase", "supply_id": supply.id, "quantity": Decimal("3.785"),
             "unit_cost": Decimal("48.877"), "reason": "F001-1"},
            {"seq": 2, "occurred_on": date(2026, 11, 2), "type": "purchase", "supply_id": supply.id, "quantity": Decimal("3.785"),
             "unit_cost": Decimal("48.877"), "reason": "F001-1"},
        ])
        assert await repo.void_movement(b.id, actor_id=ADMIN, reason="Duplicado")
        assert not await repo.void_movement(b.id, actor_id=ADMIN, reason="Otra vez")
        assert (await repo.stock_by_supply())[supply.id] == pytest.approx(3.785)
        assert [m.id for m in await repo.list_movements()] == [a.id]  # sin los anulados
        assert [m.id for m in await repo.list_movements(include_voided=True)] == [b.id, a.id]
        voided = await repo.get_movement(b.id)
        assert (voided.is_voided, voided.void_reason, voided.voided_by) == (True, "Duplicado", ADMIN)
        # Edición con historial; un anulado ya no se edita
        changes = {"quantity": {"before": 3.785, "after": 2.0}}
        assert await repo.edit_movement(a.id, {"quantity": Decimal("2")}, actor_id=ADMIN, reason="Tipeo", changes=changes)
        assert not await repo.edit_movement(b.id, {"quantity": Decimal("1")}, actor_id=ADMIN, reason="x", changes={})
        edited = await repo.get_movement(a.id)
        assert (edited.quantity, edited.edited_by) == (2.0, ADMIN) and edited.edited_at is not None
        [edit] = await repo.list_movement_edits(a.id)
        assert (edit.reason, edit.changes, edit.edited_by) == ("Tipeo", changes, ADMIN)
        assert (await repo.stock_by_supply())[supply.id] == pytest.approx(2.0)
        await session.close()
        await engine.dispose()
    _run(scenario())


# ─── Recetas ─────────────────────────────────────────────────────────────────

def test_save_recipe_versions_and_skips_empty_cells():
    repo = _Repo()
    shampoo, gloves = _supply(repo), _supply(repo, name="Guantes", content=100, cost=32)
    r1 = _save(repo, [_cell("mestizo", T2, 60, [(shampoo, 25), (gloves, 2)]), _cell("simple_short", T1)])
    assert (r1.version_label, len(r1.cells)) == ("R1", 1)  # la celda vacía no se guarda
    with pytest.raises(HTTPException) as exc:
        _save(repo, [_cell("mestizo", T2, 60, [(gloves, 2), (shampoo, 25)])])  # mismo contenido, otro orden
    assert _detail(exc)["code"] == "RECIPE_UNCHANGED"
    r2 = _save(repo, [_cell("mestizo", T2, 70, [(shampoo, 25), (gloves, 2)])])
    assert r2.version_label == "R2" and repo.recipes[r1.id].is_current is False


def test_recipe_validations():
    repo = _Repo()
    shampoo = _supply(repo)
    with pytest.raises(HTTPException) as exc:
        _save(repo, [_cell("pelaje_raro", T1, 10)])
    assert _detail(exc)["code"] == "PRICE_CATEGORY_INVALID"
    with pytest.raises(HTTPException) as exc:
        _save(repo, [_cell("mestizo", (0, 10), 10), _cell("mestizo", (5, 15), 10)])
    assert _detail(exc)["code"] == "WEIGHT_RANGE_OVERLAP"
    with pytest.raises(HTTPException) as exc:
        _save(repo, [_cell("mestizo", T1, 10, [(shampoo, 1), (shampoo, 2)])])
    assert _detail(exc)["code"] == "RECIPE_SUPPLY_REPEATED"
    with pytest.raises(HTTPException) as exc:
        _save(repo, [_cell("mestizo", T1, 10)], target_id=uuid4())
    assert exc.value.status_code == 404


def test_recipe_repository_roundtrip_sqlite():
    """Guardar y leer la tabla con el repositorio real (celdas, insumos y versión vigente)."""
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[
                SupplyModel.__table__, RecipeModel.__table__, RecipeCellModel.__table__, RecipeLineModel.__table__,
            ])
        session = async_sessionmaker(engine, expire_on_commit=False)()
        repo = PostgresInventoryRepository(session=session)
        supply = await repo.create_supply(sku="INS-001", fields={
            "name": "Shampoo", "category": "cosmetic", "purchase_unit": "Galón", "purchase_content": Decimal("3785"),
            "consumption_unit": "ml", "purchase_cost": Decimal("185"), "min_stock": Decimal("0"),
        })
        cells = [RecipeCell(breed_category="mestizo", weight_min=5.01, weight_max=15, labor_minutes=60,
                            lines=[RecipeLine(supply.id, 25)]),
                 RecipeCell(breed_category="double_long", weight_min=50.01, weight_max=None, labor_minutes=120, lines=[])]
        r1 = await repo.save_recipe_version(target_type="product", target_id=PRODUCT_ID, version=1, cells=cells,
                                            created_by=ADMIN)
        r2 = await repo.save_recipe_version(target_type="product", target_id=PRODUCT_ID, version=2, cells=cells[:1],
                                            created_by=ADMIN, replaces=r1.id)
        current = (await repo.current_recipes_for([PRODUCT_ID]))[PRODUCT_ID]
        assert (current.id, current.version_label, len(current.cells)) == (r2.id, "R2", 1)
        assert current.cells[0].lines == [RecipeLine(supply.id, 25.0)]
        history = await repo.list_recipes(current_only=False, target_id=PRODUCT_ID)
        assert [r.version for r in history] == [2, 1]
        assert [c.weight_max for c in history[1].cells if c.breed_category == "double_long"] == [None]
        with pytest.raises(ValueError):
            await repo.save_recipe_version(target_type="product", target_id=PRODUCT_ID, version=2, cells=[],
                                           created_by=ADMIN)
        await session.close()
        await engine.dispose()
    _run(scenario())


# ─── Consumo y costo por orden ───────────────────────────────────────────────

def _setup_consumption(category="double_long"):
    repo = _Repo()
    shampoo, gloves = _supply(repo), _supply(repo, name="Guantes", content=100, cost=32)
    base = _save(repo, [_cell("mestizo", T2, 60, [(shampoo, 25), (gloves, 2)]),
                        _cell("double_long", T3, 90, [(shampoo, 60), (gloves, 2)])])
    # Deslanado: solo doble manto (S4 y S5), todos los pesos, el mismo tiempo
    addon = _save(repo, [_cell(cat, tier, 20, [(shampoo, 30)]) for cat in ("double_short", "double_long")
                         for tier in (T1, T2, T3)], target_type="addon", target_id=ADDON_ID)
    pet = _pet()
    store = _Store(category)
    return SimpleNamespace(
        repo=repo, shampoo=shampoo, gloves=gloves, base=base, addon=addon, pet=pet,
        consumption=OrderConsumption(repo=repo, store_repo=store, pets_repo=_Pets(pet)),
        cost=GetOrderCost(repo=repo, store_repo=store, pets_repo=_Pets(pet)),
    )


def test_done_order_consumes_with_measured_weight_once():
    ctx = _setup_consumption()
    order = _order(ctx.pet)  # declaró 12 kg, pesó 18 kg: usa el tramo 15–25
    movements = _run(ctx.consumption.register(order))
    assert sorted((m.supply_id == ctx.shampoo.id, m.quantity) for m in movements) == [(False, -2), (True, -60), (True, -30)]
    assert {m.recipe_id for m in movements} == {ctx.base.id, ctx.addon.id}
    assert all(m.recipe_cell_id is not None and m.created_by is None and m.cost_center == "CC-PAKU01" for m in movements)
    assert movements[0].reason == "Descarga automática por receta de Spa Deluxe R1"
    with pytest.raises(HTTPException) as exc:
        _run(ctx.consumption.register(order))
    assert _detail(exc)["code"] == "CONSUMPTION_ALREADY_REGISTERED"


def test_coat_without_cell_falls_back_to_mestizo():
    ctx = _setup_consumption(category="simple_short")
    plan = _run(ctx.consumption.plan(_order(ctx.pet, measured=10.0)))
    assert [(pc.target.name, pc.category_used) for pc in plan.cells] == [("Spa Deluxe", "mestizo")]
    assert [t.name for t in plan.missing] == ["Deslanado intensivo"]  # el deslanado no aplica a pelo corto


def test_consumption_only_for_done_service_orders():
    ctx = _setup_consumption()
    with pytest.raises(HTTPException) as exc:
        _run(ctx.consumption.register(_order(ctx.pet, status=OrderStatus.in_service)))
    assert _detail(exc)["code"] == "ORDER_NOT_DONE"
    with pytest.raises(HTTPException) as exc:
        _run(ctx.consumption.register(_order(ctx.pet, parent_order_id=uuid4())))
    assert _detail(exc)["code"] == "ADJUSTMENT_ORDER"


def test_order_cost_with_labor_estimated_and_real():
    ctx = _setup_consumption()
    log = [{"step": "reception", "started_at": "2026-10-20T13:30:00+00:00"},
           {"step": "bath", "started_at": "2026-10-20T13:45:00+00:00"}]
    order = _order(ctx.pet, departed_at=datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc), service_steps_log=log)
    assert order_real_minutes(order) == (30.0, 90.0)  # 13:00 → 13:30 traslado; 13:30 → 15:00 servicio

    estimated = _run(ctx.cost.execute(order, rates=_rates(15.0)))
    supplies = round(90 * 185 / 3785 + 2 * 32 / 100, 2)
    assert (estimated.registered, estimated.supplies_cost) == (False, supplies)
    assert (estimated.estimated_minutes, estimated.labor_rate_source) == (110, "groomer")
    assert estimated.labor_cost_estimated == round(110 / 60 * 15, 2)
    assert estimated.labor_cost_real == round(90 / 60 * 15, 2)

    _run(ctx.consumption.register(order))
    _run(UpdateSupply(repo=ctx.repo).execute(ctx.shampoo.id, fields={"purchase_cost": 999}))
    registered = _run(ctx.cost.execute(order, rates=_rates(by_groomer=False)))
    assert (registered.registered, registered.supplies_cost) == (True, supplies)  # costo del momento
    assert (registered.labor_rate, registered.labor_rate_source) == (12.0, "reference")

    summary = _run(GetInventorySummary(repo=ctx.repo).execute(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31)))
    assert (summary.consumption_cost, summary.orders_with_consumption) == (supplies, 1)


def test_order_without_times_has_no_real_labor():
    ctx = _setup_consumption()
    cost = _run(ctx.cost.execute(_order(ctx.pet), rates=_rates()))
    assert (cost.real_service_minutes, cost.labor_cost_real) == (None, None)


def test_hook_is_best_effort(monkeypatch):
    calls = []

    class _Session:
        async def rollback(self):
            calls.append("rollback")

    class _Boom:
        def __init__(self, **_):
            pass

        async def register(self, order):
            raise RuntimeError("db down")

    import app.modules.inventory.app.use_cases as use_cases
    monkeypatch.setattr(use_cases, "OrderConsumption", _Boom)
    pet = _pet()
    _run(order_hook.register_order_consumption(_Session(), _order(pet)))  # no lanza
    assert calls == ["rollback"]
    _run(order_hook.register_order_consumption(_Session(), _order(pet, status=OrderStatus.in_service)))
    _run(order_hook.register_order_consumption(_Session(), _order(pet, parent_order_id=uuid4())))
    assert calls == ["rollback"]
    # Sin sesión (dobles de otros tests): tampoco lanza
    _run(order_hook.register_order_consumption(None, _order(pet)))
