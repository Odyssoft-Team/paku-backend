"""Casos de uso del inventario (feature 0009). Reglas puras en `domain/inventory.py`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.timezone import LIMA_TZ, today_lima
from app.modules.inventory.domain.inventory import (
    CATEGORIES,
    CONSUMPTION_UNITS,
    COST_CENTERS,
    LOCATIONS,
    MOVEMENT_TYPES,
    SERVICE_COST_CENTER,
    SERVICE_LOCATION,
    TARGET_TYPES,
    ConsumptionPlan,
    Recipe,
    RecipeCell,
    RecipeLine,
    Supply,
    base_weight_kg,
    next_code,
    order_targets,
    plan_consumption,
    same_cells,
    signed_quantity,
    stock_status,
)
from app.modules.store.domain.pricing import FALLBACK_CATEGORY


def _error(status_code: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})


def _invalid(code: str, message: str, **extra) -> HTTPException:
    return _error(422, code, message, **extra)


# ─── Insumos ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SupplyRow:
    supply: Supply
    stock: float
    status: str
    value: float


def supply_row(supply: Supply, stock: float) -> SupplyRow:
    stock = round(stock, 3) + 0  # "+ 0" evita -0.0
    return SupplyRow(supply, stock, stock_status(stock, supply.min_stock), max(stock, 0) * supply.unit_cost)


_SUPPLY_FIELDS = (
    "name", "category", "purchase_unit", "purchase_content", "consumption_unit", "purchase_cost",
    "min_stock", "tracks_lot", "tracks_expiry", "is_active",
)


def _supply_fields(fields: dict) -> dict:
    """Valida y normaliza los campos del maestro de insumos (solo las claves recibidas)."""
    out = {k: v for k, v in fields.items() if k in _SUPPLY_FIELDS}
    for key in ("name", "purchase_unit"):
        if key in out:
            out[key] = (out[key] or "").strip()
            if not out[key]:
                raise _invalid("SUPPLY_FIELD_REQUIRED", f"El campo {key} es obligatorio.", field=key)
    if "category" in out and out["category"] not in CATEGORIES:
        raise _invalid("SUPPLY_CATEGORY_INVALID", "Categoría inválida. Usa una de: " + ", ".join(CATEGORIES) + ".")
    if "consumption_unit" in out and out["consumption_unit"] not in CONSUMPTION_UNITS:
        raise _invalid("SUPPLY_UNIT_INVALID", "Unidad de consumo inválida. Usa una de: " + ", ".join(CONSUMPTION_UNITS) + ".")
    if "purchase_content" in out and not (out["purchase_content"] or 0) > 0:
        raise _invalid("SUPPLY_CONTENT_INVALID", "El contenido por unidad de compra debe ser mayor que 0.")
    for key in ("purchase_cost", "min_stock"):
        if key in out:
            if out[key] is None or out[key] < 0:
                raise _invalid("SUPPLY_AMOUNT_INVALID", f"El campo {key} no puede ser negativo.", field=key)
    for key in ("purchase_content", "purchase_cost", "min_stock"):
        if key in out:
            out[key] = Decimal(str(out[key]))
    return out


@dataclass
class ListSupplies:
    repo: Any

    async def execute(self, *, include_inactive: bool = True) -> list[SupplyRow]:
        supplies = await self.repo.list_supplies(include_inactive=include_inactive)
        stock = await self.repo.stock_by_supply()
        return [supply_row(s, stock.get(s.id, 0.0)) for s in supplies]


@dataclass
class CreateSupply:
    repo: Any

    async def execute(self, *, fields: dict) -> SupplyRow:
        values = _supply_fields(fields)
        for required in ("name", "category", "purchase_unit", "purchase_content", "consumption_unit", "purchase_cost"):
            if required not in values:
                raise _invalid("SUPPLY_FIELD_REQUIRED", f"El campo {required} es obligatorio.", field=required)
        values.pop("is_active", None)
        # El código lo da el backend (INS-001…). Dos altas a la vez: el segundo reintenta con el siguiente.
        for _ in range(3):
            sku = next_code(await self.repo.list_skus(), "INS-")
            try:
                supply = await self.repo.create_supply(sku=sku, fields=values)
                return supply_row(supply, 0.0)
            except ValueError as exc:
                if str(exc) != "sku_taken":
                    raise
        raise _error(status.HTTP_409_CONFLICT, "SKU_TAKEN", "No se pudo asignar un código al insumo; reintenta.")


@dataclass
class UpdateSupply:
    repo: Any

    async def execute(self, supply_id: UUID, *, fields: dict) -> SupplyRow:
        """`fields`: solo las claves enviadas. Cambiar el costo no cambia el de lo ya registrado."""
        try:
            supply = await self.repo.update_supply(supply_id, _supply_fields(fields))
        except ValueError as exc:
            if str(exc) == "supply_not_found":
                raise _error(status.HTTP_404_NOT_FOUND, "SUPPLY_NOT_FOUND", "Insumo no encontrado.") from exc
            raise
        stock = (await self.repo.stock_by_supply()).get(supply.id, 0.0)
        return supply_row(supply, stock)


# ─── Movimientos ─────────────────────────────────────────────────────────────

@dataclass
class RegisterMovement:
    """Movimiento manual. Los consumos por servicio los registra solo `OrderConsumption`."""
    repo: Any

    async def execute(
        self,
        *,
        type: str,
        supply_id: UUID,
        quantity: float,
        reason: str,
        actor_id: UUID,
        direction: Optional[str] = None,
        occurred_on: Optional[date] = None,
        location: Optional[str] = None,
        cost_center: Optional[str] = None,
        order_id: Optional[UUID] = None,
        lot: Optional[str] = None,
        expires_on: Optional[date] = None,
    ):
        if type not in MOVEMENT_TYPES:
            raise _invalid("MOVEMENT_TYPE_INVALID", "Tipo inválido. Usa uno de: " + ", ".join(MOVEMENT_TYPES) + ".")
        if not quantity or quantity <= 0:
            raise _invalid("MOVEMENT_QUANTITY_INVALID", "La cantidad debe ser mayor que 0.")
        if type == "adjustment" and direction not in ("in", "out"):
            raise _invalid("MOVEMENT_DIRECTION_REQUIRED", "Indica si el ajuste suma (in) o resta (out).")
        if not (reason or "").strip():
            raise _invalid("MOVEMENT_REASON_REQUIRED", "El motivo o comprobante es obligatorio.")
        day = occurred_on or today_lima()
        if day > today_lima():
            raise _invalid("MOVEMENT_DATE_IN_FUTURE", "La fecha del movimiento no puede ser futura.")
        if location is not None and location not in LOCATIONS:
            raise _invalid("LOCATION_INVALID", "Ubicación inválida. Usa una de: " + ", ".join(LOCATIONS) + ".")
        if cost_center is not None and cost_center not in COST_CENTERS:
            raise _invalid("COST_CENTER_INVALID", "Centro de costo inválido. Usa uno de: " + ", ".join(COST_CENTERS) + ".")
        supply = await self.repo.get_supply(supply_id)
        if supply is None:
            raise _error(status.HTTP_404_NOT_FOUND, "SUPPLY_NOT_FOUND", "Insumo no encontrado.")
        if not supply.is_active:
            raise _error(status.HTTP_409_CONFLICT, "SUPPLY_INACTIVE", "El insumo está desactivado.")
        [movement] = await self.repo.add_movements([{
            "occurred_on": day,
            "type": type,
            "supply_id": supply.id,
            "quantity": Decimal(str(signed_quantity(type, quantity, direction))),
            "unit_cost": Decimal(str(round(supply.unit_cost, 6))),
            "location": location,
            "cost_center": cost_center,
            "order_id": order_id,
            "reason": reason.strip(),
            "lot": (lot or "").strip() or None,
            "expires_on": expires_on,
            "created_by": actor_id,
        }])
        return movement


@dataclass(frozen=True)
class InventorySummary:
    inventory_value: float
    supplies_below_min: int
    consumption_cost: float
    orders_with_consumption: int
    avg_cost_per_order: Optional[float]


@dataclass
class GetInventorySummary:
    repo: Any

    async def execute(self, *, date_from: Optional[date], date_to: Optional[date]) -> InventorySummary:
        """El valor y el stock son al día de hoy; el consumo, del período."""
        rows = await ListSupplies(repo=self.repo).execute(include_inactive=False)
        cost, orders = await self.repo.consumption_totals(date_from=date_from, date_to=date_to)
        return InventorySummary(
            inventory_value=round(sum(r.value for r in rows), 2),
            supplies_below_min=sum(1 for r in rows if r.status != "ok"),
            consumption_cost=round(cost, 2),
            orders_with_consumption=orders,
            avg_cost_per_order=round(cost / orders, 2) if orders else None,
        )


# ─── Recetas ─────────────────────────────────────────────────────────────────

def recipe_cells(cells: list[dict], supplies: dict[UUID, Supply]) -> list[RecipeCell]:
    """Valida las celdas de una tabla de receta (como la de precios) y las convierte."""
    from app.modules.store.app.use_cases_impl.pricing_admin import validate_matrix

    # Misma validación que la tabla de precios: pelajes válidos y tramos que no se superponen
    validate_matrix([{**c, "price": 0} for c in cells])
    out: list[RecipeCell] = []
    for c in cells:
        labor = float(c.get("labor_minutes") or 0)
        if labor < 0:
            raise _invalid("LABOR_MINUTES_INVALID", "Los minutos de groomer no pueden ser negativos.")
        seen: set[UUID] = set()
        lines: list[RecipeLine] = []
        for line in c.get("lines") or []:
            supply_id, quantity = line["supply_id"], line["quantity"]
            if supply_id in seen:
                raise _invalid("RECIPE_SUPPLY_REPEATED", "Un insumo aparece dos veces en la misma celda.",
                               supply_id=str(supply_id))
            if supply_id not in supplies:
                raise _invalid("SUPPLY_NOT_FOUND", "Insumo no encontrado.", supply_id=str(supply_id))
            if not quantity or quantity <= 0:
                raise _invalid("RECIPE_QUANTITY_INVALID", "Cada insumo necesita una cantidad mayor que 0.",
                               supply_id=str(supply_id))
            seen.add(supply_id)
            lines.append(RecipeLine(supply_id=supply_id, quantity=float(quantity)))
        if not lines and labor == 0:
            continue  # celda vacía: no se guarda
        out.append(RecipeCell(breed_category=c["breed_category"], weight_min=float(c["weight_min"]),
                              weight_max=None if c.get("weight_max") is None else float(c["weight_max"]),
                              labor_minutes=labor, lines=lines))
    return out


def cell_supplies_cost(cell: RecipeCell, supplies: dict[UUID, Supply]) -> float:
    """Costo de los insumos de una celda con los costos actuales."""
    return sum(supplies[l.supply_id].unit_cost * l.quantity for l in cell.lines if l.supply_id in supplies)


@dataclass
class SaveRecipe:
    """Guarda la tabla completa de un servicio o adicional como la versión siguiente (R1 → R2)."""
    repo: Any
    store_repo: Any

    async def execute(self, *, target_type: str, target_id: UUID, cells: list[dict], actor_id: UUID) -> Recipe:
        if target_type not in TARGET_TYPES:
            raise _invalid("RECIPE_TARGET_INVALID", "target_type debe ser 'product' o 'addon'.")
        getter = self.store_repo.get_product if target_type == "product" else self.store_repo.get_addon
        if await getter(target_id) is None:
            raise _error(status.HTTP_404_NOT_FOUND, "TARGET_NOT_FOUND", "Servicio o adicional no encontrado.")
        supplies = await self.repo.get_supplies(list({l["supply_id"] for c in cells for l in c.get("lines") or []}))
        new_cells = recipe_cells(cells, supplies)
        current = (await self.repo.current_recipes_for([target_id])).get(target_id)
        if same_cells(new_cells, current.cells if current else []):
            raise _error(status.HTTP_409_CONFLICT, "RECIPE_UNCHANGED", "La receta no tiene cambios.")
        try:
            return await self.repo.save_recipe_version(
                target_type=target_type, target_id=target_id, version=(current.version + 1) if current else 1,
                cells=new_cells, created_by=actor_id, replaces=current.id if current else None,
            )
        except ValueError as exc:
            if str(exc) == "recipe_version_taken":
                raise _error(status.HTTP_409_CONFLICT, "RECIPE_NOT_CURRENT",
                             "Otra persona guardó la receta; recarga y vuelve a intentar.") from exc
            raise


# ─── Consumo y costo por orden ───────────────────────────────────────────────

def _lima_day(when) -> Optional[date]:
    if when is None:
        return None
    if when.tzinfo is None:  # la BD guarda en UTC
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(LIMA_TZ).date()


def _completed_day(order) -> date:
    return _lima_day(order.completed_at or order.updated_at) or today_lima()


def _minutes(start, end) -> Optional[float]:
    if start is None or end is None:
        return None
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    if isinstance(end, str):
        end = datetime.fromisoformat(end)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return round(max((end - start).total_seconds(), 0) / 60, 1)


def order_real_minutes(order) -> tuple[Optional[float], Optional[float]]:
    """(traslado, servicio) registrados, como la pantalla Tiempos: traslado = salida → llegada (inicio de
    "recepción"); servicio = llegada → fin. None si falta algún tiempo."""
    log = order.service_steps_log or []
    arrival = next((e.get("started_at") for e in log if isinstance(e, dict) and e.get("step") == "reception"), None)
    return _minutes(order.departed_at, arrival), _minutes(arrival, order.completed_at)


def _base_pet_id(items_snapshot) -> Optional[UUID]:
    for line in items_snapshot or []:
        if isinstance(line, dict) and line.get("kind") == "service_base":
            meta = line.get("meta") if isinstance(line.get("meta"), dict) else {}
            try:
                return UUID(str(meta.get("pet_id")))
            except ValueError:
                return None
    return None


@dataclass
class OrderConsumption:
    """Consumo de insumos de una orden según sus recetas (servicio base + adicionales)."""
    repo: Any
    store_repo: Any
    pets_repo: Any

    async def plan(self, order) -> ConsumptionPlan:
        targets = order_targets(order.items_snapshot)
        ids = []
        for t in targets:
            try:
                ids.append(UUID(t.ref_id))
            except ValueError:
                pass
        recipes = {str(k): v for k, v in (await self.repo.current_recipes_for(ids)).items()}

        # Fila de la tabla: la misma categoría de precio de la mascota (pelaje de la raza o "mestizo")
        category = FALLBACK_CATEGORY
        pet_id = _base_pet_id(order.items_snapshot)
        if pet_id is not None:
            pet = await self.pets_repo.get_by_id(pet_id, include_deleted=True)
            if pet is not None:
                category = await self.store_repo.price_category_for(pet.breed_id)
        weight = base_weight_kg(order.items_snapshot, order.measured_weight_kg)
        return plan_consumption(targets, recipes, breed_category=category, weight_kg=weight)

    async def register(self, order, *, actor_id: Optional[UUID] = None) -> list:
        """Registra el consumo de una orden terminada una sola vez. Devuelve los movimientos creados."""
        from app.modules.orders.domain.order import OrderStatus

        if order.status != OrderStatus.done:
            raise _error(status.HTTP_409_CONFLICT, "ORDER_NOT_DONE", "Solo se descuentan insumos de una orden terminada.")
        if order.parent_order_id is not None:
            raise _error(status.HTTP_409_CONFLICT, "ADJUSTMENT_ORDER", "Las órdenes de ajuste no consumen insumos.")
        if await self.repo.has_order_consumption(order.id):
            raise _error(status.HTTP_409_CONFLICT, "CONSUMPTION_ALREADY_REGISTERED",
                         "El consumo de esta orden ya está registrado.")
        plan = await self.plan(order)
        supplies = await self.repo.get_supplies(list({line.supply_id for _, line in plan.lines}))
        day = _completed_day(order)
        rows = []
        for planned, line in plan.lines:
            supply = supplies.get(line.supply_id)
            if supply is None:
                continue
            rows.append({
                "occurred_on": day,
                "type": "consumption",
                "supply_id": supply.id,
                "quantity": Decimal(str(-abs(line.quantity))),
                "unit_cost": Decimal(str(round(supply.unit_cost, 6))),
                "location": SERVICE_LOCATION,
                "cost_center": SERVICE_COST_CENTER,
                "order_id": order.id,
                "recipe_id": planned.recipe.id,
                "recipe_cell_id": planned.cell.id,
                "reason": f"Descarga automática por receta de {planned.target.name} {planned.recipe.version_label}",
                "created_by": actor_id,
            })
        return await self.repo.add_movements(rows) if rows else []


@dataclass(frozen=True)
class OrderCostLine:
    supply: Supply
    quantity: float          # positiva (lo que se consume)
    unit_cost: float
    recipe: Optional[Recipe]

    @property
    def cost(self) -> float:
        return self.quantity * self.unit_cost


@dataclass(frozen=True)
class OrderCost:
    order: Any
    registered: bool              # True: insumos ya registrados; False: estimado con las recetas vigentes
    plan: ConsumptionPlan         # celdas de las recetas vigentes (minutos estimados)
    lines: list[OrderCostLine]
    labor_rate: Optional[float]   # S/ por hora de servicio
    labor_rate_source: str        # groomer | reference
    real_travel_minutes: Optional[float]
    real_service_minutes: Optional[float]

    @property
    def supplies_cost(self) -> float:
        return round(sum(line.cost for line in self.lines), 2)

    @property
    def estimated_minutes(self) -> float:
        return self.plan.labor_minutes

    @property
    def labor_cost_estimated(self) -> Optional[float]:
        return None if self.labor_rate is None else round(self.estimated_minutes / 60 * self.labor_rate, 2)

    @property
    def labor_cost_real(self) -> Optional[float]:
        if self.labor_rate is None or self.real_service_minutes is None:
            return None
        return round(self.real_service_minutes / 60 * self.labor_rate, 2)


@dataclass
class GetOrderCost:
    repo: Any
    store_repo: Any
    pets_repo: Any

    async def execute(self, order, *, rates) -> OrderCost:
        """`rates`: tarifas de mano de obra (`groomer_costs.app.use_cases.LaborRates`) del día de la orden."""
        consumption = OrderConsumption(repo=self.repo, store_repo=self.store_repo, pets_repo=self.pets_repo)
        plan = await consumption.plan(order)
        rate, source = rates.rate_for(order.groomer_id)
        travel, service = order_real_minutes(order)
        movements = await self.repo.list_movements(order_id=order.id, type="consumption", limit=1000)
        if movements:
            supplies = await self.repo.get_supplies(list({m.supply_id for m in movements}))
            recipes = await self.repo.get_recipes(list({m.recipe_id for m in movements if m.recipe_id}))
            lines = [
                OrderCostLine(supplies[m.supply_id], -m.quantity, m.unit_cost, recipes.get(m.recipe_id))
                for m in sorted(movements, key=lambda m: m.seq) if m.supply_id in supplies
            ]
            return OrderCost(order, True, plan, lines, rate, source, travel, service)
        supplies = await self.repo.get_supplies(list({line.supply_id for _, line in plan.lines}))
        lines = [
            OrderCostLine(supplies[line.supply_id], line.quantity, supplies[line.supply_id].unit_cost, planned.recipe)
            for planned, line in plan.lines if line.supply_id in supplies
        ]
        return OrderCost(order, False, plan, lines, rate, source, travel, service)


async def order_labor_rates(session, order):
    """Tarifas de mano de obra vigentes el día en que terminó la orden (o hoy)."""
    from app.modules.groomer_costs.app.use_cases import labor_rates

    return await labor_rates(session, day=_completed_day(order))
