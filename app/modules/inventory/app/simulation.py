"""Simulador de un servicio (feature 0019): servicio + adicionales + raza + peso → insumos, costo, precio y margen.

Usa las mismas reglas que una orden real: la celda de la receta vigente según el pelaje de la raza (o «mestizo») y
el tramo del peso (`plan_consumption`), el precio de la tabla de precios con la misma regla, y la mano de obra con
el costo por hora del groomer elegido o el de referencia. No registra nada.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.inventory.domain.inventory import (
    ConsumptionPlan,
    ConsumptionTarget,
    Supply,
    plan_consumption,
    stock_status,
    weight_code_for,
)
from app.modules.store.domain.pricing import FALLBACK_CATEGORY, category_label

MAX_WEIGHT_KG = 150


def _error(status_code: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})


@dataclass(frozen=True)
class SimLine:
    """Un insumo de una celda (servicio o adicional)."""
    supply: Supply
    quantity: float

    @property
    def cost(self) -> float:
        return self.quantity * self.supply.unit_cost


@dataclass(frozen=True)
class SimItem:
    target: ConsumptionTarget
    price: Optional[float]                 # None: sin precio en la tabla para este pelaje y peso
    recipe_version: Optional[str]          # None: sin receta o sin celda para este pelaje y peso
    category_used: Optional[str]
    weight_min: Optional[float]
    weight_max: Optional[float]
    labor_minutes: float
    lines: list[SimLine]

    @property
    def supplies_cost(self) -> float:
        return sum(l.cost for l in self.lines)


@dataclass(frozen=True)
class SimSupply:
    """Consumo total de un insumo en el servicio simulado, frente a su stock de hoy."""
    supply: Supply
    quantity: float
    stock: float

    @property
    def cost(self) -> float:
        return self.quantity * self.supply.unit_cost

    @property
    def services_with_stock(self) -> Optional[int]:
        """Cuántos servicios iguales alcanzan con el stock actual (solo por este insumo)."""
        if self.quantity <= 0:
            return None
        return max(0, math.floor(round(self.stock / self.quantity, 6)))

    @property
    def stock_status(self) -> str:
        return stock_status(self.stock, self.supply.min_stock)


@dataclass
class Simulation:
    product: Any
    breed_id: Optional[str]
    breed_name: Optional[str]
    breed_category: str
    weight_kg: float
    items: list[SimItem]
    supplies: list[SimSupply]
    labor_rate: Optional[float]
    labor_rate_source: str                 # groomer | reference
    warnings: list[str] = field(default_factory=list)

    @property
    def price(self) -> Optional[float]:
        prices = [i.price for i in self.items]
        return None if any(p is None for p in prices) else round(sum(prices), 2)

    @property
    def supplies_cost(self) -> float:
        return round(sum(i.supplies_cost for i in self.items), 2)

    @property
    def labor_minutes(self) -> float:
        return sum(i.labor_minutes for i in self.items)

    @property
    def labor_cost(self) -> Optional[float]:
        return None if self.labor_rate is None else round(self.labor_minutes / 60 * self.labor_rate, 2)

    @property
    def total_cost(self) -> Optional[float]:
        return None if self.labor_cost is None else round(self.supplies_cost + self.labor_cost, 2)

    @property
    def margin(self) -> Optional[float]:
        if self.price is None or self.total_cost is None:
            return None
        return round(self.price - self.total_cost, 2)

    @property
    def margin_pct(self) -> Optional[float]:
        if self.margin is None or not self.price:
            return None
        return round(self.margin / self.price * 100, 1)

    @property
    def weight_code(self) -> Optional[str]:
        return weight_code_for(self.weight_kg)

    @property
    def category_label(self) -> str:
        return category_label(self.breed_category)


@dataclass
class SimulateService:
    repo: Any          # PostgresInventoryRepository
    store_repo: Any    # PostgresStoreRepository
    breeds_repo: Any   # algo con get(breed_id) → BreedModel | None

    async def execute(self, *, product_id: UUID, addon_ids: list[UUID], breed_id: Optional[str],
                      weight_kg: float, rates) -> Simulation:
        """`rates`: `(costo por hora, "groomer" | "reference")`, de `LaborRates.rate_for(groomer_id)`."""
        if weight_kg is None or weight_kg <= 0 or weight_kg > MAX_WEIGHT_KG:
            raise _error(422, "WEIGHT_INVALID", f"El peso debe ser mayor que 0 y hasta {MAX_WEIGHT_KG} kg.")
        product = await self.store_repo.get_product(product_id)
        if product is None:
            raise _error(status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_FOUND", "Servicio no encontrado.")
        addons = []
        for addon_id in dict.fromkeys(addon_ids):
            addon = await self.store_repo.get_addon(addon_id)
            if addon is None:
                raise _error(status.HTTP_404_NOT_FOUND, "ADDON_NOT_FOUND", "Adicional no encontrado.",
                             addon_id=str(addon_id))
            if addon.product_id != product.id:
                raise _error(422, "ADDON_NOT_IN_SERVICE", f"«{addon.name}» no es un adicional de este servicio.",
                             addon_id=str(addon_id))
            addons.append(addon)

        breed_name = None
        warnings: list[str] = []
        if breed_id:
            breed = await self.breeds_repo.get(breed_id)
            if breed is None:
                raise _error(status.HTTP_404_NOT_FOUND, "BREED_NOT_FOUND", "Raza no encontrada.")
            breed_name = breed.name
            category = await self.store_repo.price_category_for(breed_id)
        else:
            category = FALLBACK_CATEGORY
        if product.max_weight_kg is not None and weight_kg > product.max_weight_kg:
            warnings.append(f"El servicio admite hasta {product.max_weight_kg:g} kg; en la app no se podría comprar.")
        if not product.is_active:
            warnings.append("El servicio está inactivo.")
        for a in addons:
            if not a.is_active:
                warnings.append(f"El adicional «{a.name}» está inactivo.")

        targets = [ConsumptionTarget("product", str(product.id), product.name)] + [
            ConsumptionTarget("addon", str(a.id), a.name) for a in addons
        ]
        recipes = {str(k): v for k, v in (await self.repo.current_recipes_for(
            [product.id] + [a.id for a in addons])).items()}
        plan: ConsumptionPlan = plan_consumption(targets, recipes, breed_category=category, weight_kg=weight_kg)
        supplies = await self.repo.get_supplies(list({line.supply_id for _, line in plan.lines}))

        cells = {pc.target.ref_id: pc for pc in plan.cells}
        items: list[SimItem] = []
        for t in targets:
            price = await self.store_repo.price_for(target_id=UUID(t.ref_id), target_type=t.target_type,
                                                    species=product.species, breed_category=category,
                                                    weight=weight_kg)
            pc = cells.get(t.ref_id)
            if pc is None:
                items.append(SimItem(t, price, None, None, None, None, 0, []))
                continue
            lines = [SimLine(supplies[l.supply_id], l.quantity) for l in pc.cell.lines if l.supply_id in supplies]
            items.append(SimItem(t, price, pc.recipe.version_label, pc.category_used, pc.cell.weight_min,
                                 pc.cell.weight_max, pc.cell.labor_minutes, lines))

        for i in items:
            if i.recipe_version is None:
                warnings.append(f"«{i.target.name}» no tiene receta para este pelaje y peso: no suma insumos ni minutos.")
            if i.price is None:
                warnings.append(f"«{i.target.name}» no tiene precio para este pelaje y peso.")

        totals: dict[UUID, float] = {}
        for i in items:
            for l in i.lines:
                totals[l.supply.id] = totals.get(l.supply.id, 0) + l.quantity
        stock = await self.repo.stock_by_supply()
        sim_supplies = sorted(
            (SimSupply(supplies[sid], qty, stock.get(sid, 0.0)) for sid, qty in totals.items()),
            key=lambda s: -s.cost,
        )
        rate, source = rates
        if rate is None:
            warnings.append("No hay costo por hora de groomer registrado: falta la mano de obra.")
        return Simulation(product=product, breed_id=breed_id, breed_name=breed_name, breed_category=category,
                          weight_kg=weight_kg, items=items, supplies=sim_supplies, labor_rate=rate,
                          labor_rate_source=source, warnings=warnings)
