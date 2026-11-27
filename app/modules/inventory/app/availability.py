"""Disponibilidad de insumos para vender servicios (feature 0025).

Lo usan la tienda (marcar «no disponible» un servicio o adicional para una mascota) y el pago de una orden (no se
cobra si su servicio no se puede hacer). Reglas en `domain/availability.py`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException

from app.modules.inventory.domain.availability import Shortage, merge, needs_of, shortage_message, shortages
from app.modules.inventory.domain.inventory import ConsumptionTarget, plan_consumption

logger = logging.getLogger(__name__)


def _uuid(value) -> Optional[UUID]:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


@dataclass
class StockAvailability:
    repo: Any            # PostgresInventoryRepository
    consumption: Any     # OrderConsumption (plan de cada orden vendida: su pelaje y peso)
    _available: dict = field(default_factory=dict, init=False)   # exclude_order_id → disponible

    async def available(self, *, exclude_order_id: Optional[UUID] = None) -> dict[UUID, float]:
        """Stock − consumo comprometido de los servicios vendidos que aún no se realizan."""
        if exclude_order_id in self._available:
            return self._available[exclude_order_id]
        stock = dict(await self.repo.stock_by_supply())
        for order in await self.repo.sold_pending_orders(exclude_order_id=exclude_order_id):
            try:
                plan = await self.consumption.plan(order)
            except Exception:   # una orden que no se puede planear no compromete insumos; no bloquea la venta
                logger.exception("availability: no se pudo planear la orden %s", order.id)
                continue
            for _, line in plan.lines:
                stock[line.supply_id] = stock.get(line.supply_id, 0.0) - float(line.quantity)
        self._available[exclude_order_id] = stock
        return stock

    async def for_pet(
        self, targets: list[ConsumptionTarget], *, breed_category: str, weight_kg: float,
        base: Optional[ConsumptionTarget] = None,
    ) -> dict[str, list[Shortage]]:
        """Faltantes de cada servicio o adicional (por `ref_id`) para una mascota. Un adicional se evalúa junto con
        `base` (su servicio). Lista vacía = disponible (también sin receta o sin celda que aplique)."""
        everything = targets + ([base] if base is not None else [])
        ids = list({u for t in everything if (u := _uuid(t.ref_id)) is not None})
        recipes = {str(k): v for k, v in (await self.repo.current_recipes_for(ids)).items()}
        plan = plan_consumption(everything, recipes, breed_category=breed_category, weight_kg=weight_kg)
        by_target = {pc.target.ref_id: needs_of(pc.cell.lines) for pc in plan.cells}
        base_needs = by_target.get(base.ref_id, {}) if base is not None else {}
        if not any(by_target.values()):
            return {t.ref_id: [] for t in targets}
        available = await self.available()
        supplies = await self.repo.get_supplies(list({sid for n in by_target.values() for sid in n}))
        out = {}
        for t in targets:
            own = by_target.get(t.ref_id, {})
            needs = own if base is None or t.ref_id == base.ref_id else merge(own, base_needs)
            out[t.ref_id] = shortages(needs, available, supplies) if own else []
        return out

    async def order_shortages(self, order) -> list[Shortage]:
        """Faltantes de una orden completa (servicio y adicionales), sin contar su propio consumo."""
        plan = await self.consumption.plan(order)
        needs = needs_of(line for _, line in plan.lines)
        if not needs:
            return []
        available = await self.available(exclude_order_id=order.id)
        supplies = await self.repo.get_supplies(list(needs))
        return shortages(needs, available, supplies)


def out_of_stock_error(items: list[Shortage]) -> HTTPException:
    return HTTPException(status_code=409, detail={
        "code": "OUT_OF_STOCK",
        "message": f"Este servicio no está disponible por ahora: {shortage_message(items).lower()}. "
                   "No se realizó ningún cobro.",
        "supplies": [s.name for s in items],
    })


def stock_availability(session) -> StockAvailability:
    """Con los repositorios reales."""
    from app.core.db import engine
    from app.modules.inventory.app.use_cases import OrderConsumption
    from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
    from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
    from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

    repo = PostgresInventoryRepository(session=session)
    return StockAvailability(repo=repo, consumption=OrderConsumption(
        repo=repo, store_repo=PostgresStoreRepository(session=session, engine=engine),
        pets_repo=PostgresPetRepository(session=session, engine=engine)))
