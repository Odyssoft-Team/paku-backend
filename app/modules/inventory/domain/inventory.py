"""Inventario de insumos (feature 0009).

- El stock de un insumo es la suma de sus movimientos (con signo). Nada se borra: los errores se corrigen
  con un ajuste.
- Cada movimiento guarda el costo por unidad de consumo vigente al registrarlo; cambiar después el costo
  del insumo no cambia el costo de lo ya consumido.
- Las recetas tienen la misma forma que la tabla de precios: una tabla por servicio y por adicional, con
  filas = tipo de pelaje (+ "mestizo") y columnas = tramos de peso. Cada celda dice qué insumos se gastan y
  cuántos minutos de groomer toma. Guardar la tabla crea la versión siguiente (R1 → R2).
- Al terminar una orden se usa la celda que corresponde, con la misma regla que el precio (`find_cell`):
  el pelaje de la raza o, si esa fila no tiene la celda, la fila "mestizo"; el tramo que contiene el peso.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from app.modules.store.domain.pricing import DEFAULT_WEIGHT_TIERS, FALLBACK_CATEGORY

# ─── Listas fijas (GET /admin/inventory/config) ──────────────────────────────

CATEGORIES: dict[str, str] = {
    "cosmetic": "Cosmético",
    "hygiene": "Higiene",
    "consumable": "Consumible",
    "cleaning": "Limpieza",
    "spare_part": "Repuesto",
}
CONSUMPTION_UNITS: tuple[str, ...] = ("ml", "g", "unidad")

# Ubicaciones y centros de costo (confirmados por el dueño 2026-10-29: una sola van por ahora)
LOCATIONS: tuple[str, ...] = ("Almacén central", "Paku 01")
COST_CENTERS: dict[str, str] = {
    "CC-PAKU01": "Paku Spa – Unidad 01",
    "CC-SPA-GEN": "Paku Spa – General (almacén)",
    "CC-ADM": "Administración",
}
# Dónde se registra el consumo automático de una orden (una sola van)
SERVICE_LOCATION = "Paku 01"
SERVICE_COST_CENTER = "CC-PAKU01"

# Tipo de movimiento → signo de la cantidad (0 = lo decide la dirección del ajuste)
MOVEMENT_TYPES: dict[str, tuple[str, int]] = {
    "initial_stock": ("Stock inicial", 1),
    "purchase": ("Compra", 1),
    "consumption": ("Consumo servicio", -1),
    "adjustment": ("Ajuste", 0),
    "waste": ("Merma", -1),
}

# Tramos de peso del documento (W01…W06) = tramos de la tabla de precios. Solo para mostrar el tamaño de una
# mascota (CRM); las recetas guardan el tramo como en los precios (weight_min / weight_max).
WEIGHT_CODES: dict[str, tuple[float, Optional[float]]] = {
    f"W{i:02d}": tier for i, tier in enumerate(DEFAULT_WEIGHT_TIERS, start=1)
}

TARGET_TYPES: tuple[str, ...] = ("product", "addon")


def weight_code_for(weight_kg: Optional[float]) -> Optional[str]:
    """Tramo de peso (W01…W06) para un peso en kg; None si no hay peso."""
    if weight_kg is None:
        return None
    # Primer tramo cuyo tope alcanza el peso (los tramos son contiguos: 5 kg es W01, 5,005 kg es W02)
    for code, (_, high) in WEIGHT_CODES.items():
        if high is None or weight_kg <= high:
            return code
    return None


# ─── Entidades ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Supply:
    id: UUID
    sku: str
    name: str
    category: str
    purchase_unit: str
    purchase_content: float       # contenido de una unidad de compra, en unidad de consumo
    consumption_unit: str
    purchase_cost: float          # S/ por unidad de compra
    min_stock: float              # en unidad de consumo
    tracks_lot: bool
    tracks_expiry: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @property
    def unit_cost(self) -> float:
        """S/ por unidad de consumo."""
        return self.purchase_cost / self.purchase_content if self.purchase_content else 0.0


@dataclass(frozen=True)
class Movement:
    id: UUID
    seq: int
    occurred_on: date
    type: str
    supply_id: UUID
    quantity: float               # + entra, − sale (unidad de consumo)
    unit_cost: float              # costo por unidad al registrarlo
    location: Optional[str]
    cost_center: Optional[str]
    reason: str
    created_at: datetime
    order_id: Optional[UUID] = None
    recipe_id: Optional[UUID] = None
    recipe_cell_id: Optional[UUID] = None
    lot: Optional[str] = None
    expires_on: Optional[date] = None
    created_by: Optional[UUID] = None   # None = sistema (consumo automático)
    created_by_name: Optional[str] = None

    @property
    def code(self) -> str:
        return f"MOV-{self.seq:04d}"

    @property
    def cost(self) -> float:
        return self.quantity * self.unit_cost


@dataclass(frozen=True)
class RecipeLine:
    supply_id: UUID
    quantity: float


@dataclass(frozen=True)
class RecipeCell:
    """Una celda de la tabla: pelaje × tramo de peso → insumos y minutos de groomer."""
    breed_category: str
    weight_min: float
    weight_max: Optional[float]      # None = sin tope
    labor_minutes: float
    lines: list[RecipeLine]
    id: Optional[UUID] = None

    def contains(self, weight: float) -> bool:
        return self.weight_min <= weight and (self.weight_max is None or weight <= self.weight_max)

    def key(self) -> tuple:
        lines = tuple(sorted((str(l.supply_id), round(l.quantity, 3)) for l in self.lines))
        return (self.breed_category, round(self.weight_min, 2),
                None if self.weight_max is None else round(self.weight_max, 2), round(self.labor_minutes, 2), lines)


@dataclass(frozen=True)
class Recipe:
    """Tabla de consumo de un servicio (product) o adicional (addon). Una fila por versión."""
    id: UUID
    target_type: str
    target_id: UUID
    version: int
    is_current: bool
    cells: list[RecipeCell]
    created_at: datetime
    created_by: Optional[UUID] = None

    @property
    def version_label(self) -> str:
        return f"R{self.version}"


# ─── Reglas ──────────────────────────────────────────────────────────────────

def stock_status(stock: float, min_stock: float) -> str:
    """`out` (agotado), `low` (bajo el mínimo) u `ok`."""
    if stock <= 0:
        return "out"
    return "low" if stock < min_stock else "ok"


def signed_quantity(movement_type: str, quantity: float, direction: Optional[str] = None) -> float:
    """Cantidad con signo según el tipo; el ajuste usa `direction` (`in` | `out`, por defecto `out`)."""
    sign = MOVEMENT_TYPES[movement_type][1]
    if sign == 0:
        sign = 1 if direction == "in" else -1
    return sign * abs(quantity)


def next_code(existing: list[str], prefix: str, width: int = 3) -> str:
    """Correlativo siguiente para `prefix` (INS-) entre los códigos existentes."""
    numbers = []
    for code in existing:
        rest = code[len(prefix):] if code.startswith(prefix) else ""
        if rest.isdigit():
            numbers.append(int(rest))
    return f"{prefix}{(max(numbers) if numbers else 0) + 1:0{width}d}"


def same_cells(a: list[RecipeCell], b: list[RecipeCell]) -> bool:
    return sorted(c.key() for c in a) == sorted(c.key() for c in b)


def find_cell(cells: list[RecipeCell], *, breed_category: str, weight: float) -> tuple[Optional[RecipeCell], Optional[str]]:
    """Celda que aplica y su fila, con la regla del precio (`price_detail_for`): la fila del pelaje y, si no
    tiene esa celda, la fila "mestizo"; el tramo que contiene el peso (redondeado hacia arriba al centésimo)."""
    weight = math.ceil(round(float(weight), 6) * 100) / 100

    def _in(category: str) -> Optional[RecipeCell]:
        found = [c for c in cells if c.breed_category == category and c.contains(weight)]
        return max(found, key=lambda c: c.weight_min) if found else None

    cell = _in(breed_category)
    if cell is not None:
        return cell, breed_category
    if breed_category != FALLBACK_CATEGORY:
        cell = _in(FALLBACK_CATEGORY)
        if cell is not None:
            return cell, FALLBACK_CATEGORY
    return None, None


@dataclass(frozen=True)
class ConsumptionTarget:
    """Algo de la orden que consume insumos: el servicio base o un adicional."""
    target_type: str               # product | addon
    ref_id: str                    # id del producto o del adicional en la orden
    name: str


@dataclass(frozen=True)
class PlannedCell:
    target: ConsumptionTarget
    recipe: Recipe
    cell: RecipeCell
    category_used: str             # fila usada (el pelaje o "mestizo")


@dataclass
class ConsumptionPlan:
    breed_category: str
    weight_kg: Optional[float]
    cells: list[PlannedCell] = field(default_factory=list)
    missing: list[ConsumptionTarget] = field(default_factory=list)

    @property
    def lines(self) -> list[tuple[PlannedCell, RecipeLine]]:
        return [(pc, line) for pc in self.cells for line in pc.cell.lines]

    @property
    def labor_minutes(self) -> float:
        return sum(pc.cell.labor_minutes for pc in self.cells)


def order_targets(items_snapshot: Any) -> list[ConsumptionTarget]:
    """Servicio base y adicionales de la orden (desde `items_snapshot`)."""
    out: list[ConsumptionTarget] = []
    for line in items_snapshot or []:
        if not isinstance(line, dict):
            continue
        kind = line.get("kind")
        ref = str(line.get("ref_id") or "")
        if kind == "service_base":
            out.append(ConsumptionTarget("product", ref, line.get("name") or "Servicio"))
        elif kind == "service_addon":
            out.append(ConsumptionTarget("addon", ref, line.get("name") or "Adicional"))
    return out


def base_weight_kg(items_snapshot: Any, measured_weight_kg: Optional[float]) -> Optional[float]:
    """Peso para elegir el tramo: el medido en el servicio (siempre se pesa) o, si falta, el declarado."""
    if measured_weight_kg is not None:
        return float(measured_weight_kg)
    for line in items_snapshot or []:
        if isinstance(line, dict) and line.get("kind") == "service_base":
            meta = line.get("meta") if isinstance(line.get("meta"), dict) else {}
            if meta.get("pet_weight_kg") is not None:
                return float(meta["pet_weight_kg"])
    return None


def plan_consumption(
    targets: list[ConsumptionTarget],
    recipes_by_target: dict[str, Recipe],
    *,
    breed_category: str,
    weight_kg: Optional[float],
) -> ConsumptionPlan:
    """Celdas de receta que usa una orden (sin tocar la base de datos). Sin peso no hay celda."""
    plan = ConsumptionPlan(breed_category=breed_category, weight_kg=weight_kg)
    for target in targets:
        recipe = recipes_by_target.get(target.ref_id)
        cell, used = (None, None)
        if recipe is not None and weight_kg is not None:
            cell, used = find_cell(recipe.cells, breed_category=breed_category, weight=weight_kg)
        if cell is None:
            plan.missing.append(target)
            continue
        plan.cells.append(PlannedCell(target, recipe, cell, used))
    return plan
