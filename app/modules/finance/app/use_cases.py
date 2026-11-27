"""Cierre mensual / P&L (feature 0024): junta órdenes, comprobantes, inventario y costo del groomer de un mes.

Solo lectura. Reutiliza el plan de consumo de Inventario (`OrderConsumption.plan_with`) con la versión de la receta
que regía el día de cada servicio, y las tarifas de `groomer_costs` de ese día.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Optional
from uuid import UUID

from app.core.timezone import LIMA_TZ, today_lima
from app.modules.finance.domain.pnl import (
    CancelledPaid,
    GroomerMonth,
    MonthlyPnl,
    MovementFact,
    SaleFact,
    ServiceCost,
    build_pnl,
    month_period,
    net_of_igv,
    r2,
    recipe_on,
)
from app.modules.finance.infra.postgres_finance_read_repository import full_name
from app.modules.groomer_costs.app.use_cases import rates_from_profiles
from app.modules.groomer_costs.domain.costs import profile_on
from app.modules.inventory.app.use_cases import order_real_minutes
from app.modules.inventory.domain.inventory import order_targets

logger = logging.getLogger(__name__)


def lima_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=LIMA_TZ).astimezone(timezone.utc)


def lima_day(when: Optional[datetime]) -> Optional[date]:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(LIMA_TZ).date()


def _f(value) -> float:
    return float(value or 0)


def _uuid(value) -> Optional[UUID]:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


@dataclass
class BuildMonthlyPnl:
    repo: Any              # PostgresFinanceReadRepository
    inventory_repo: Any    # PostgresInventoryRepository (recipes_for)
    cost_repo: Any         # PostgresCostRepository (list_profiles)
    consumption: Any       # inventory OrderConsumption (plan_with: fila del pelaje y tramo de peso)
    settings: Callable     # async (key) -> valor efectivo de Parámetros generales
    today: Callable[[], date] = today_lima

    async def execute(self, *, month: str) -> MonthlyPnl:
        period = month_period(month, self.today())   # ValueError → 422 en el router
        start, end = lima_start(period.start), lima_start(period.end + timedelta(days=1))
        igv = _f(await self.settings("igv_percent"))
        fee_card = await self.settings("pos_fee_card_percent")
        fee_yape = await self.settings("pos_fee_yape_percent")

        services = await self.repo.services_done(start, end)
        adjustments = await self.repo.adjustments_of([o.id for o in services])
        cancelled_orders = await self.repo.cancelled_paid(start, end)
        docs = await self.repo.valid_documents([o.id for o in services] + [a.id for a in adjustments])
        users = await self.repo.users_by_id([o.user_id for o in services] + [o.groomer_id for o in services]
                                            + [o.user_id for o in cancelled_orders])
        pets = await self.repo.order_pet_names([o.id for o in services])
        day_of = {o.id: lima_day(o.completed_at or o.updated_at) for o in services}

        def sale(o, kind: str, day: date) -> SaleFact:
            total = _f(o.total_snapshot)
            doc = docs.get(o.id)
            return SaleFact(
                order_id=o.id, kind=kind, parent_order_id=o.parent_order_id, day=day, total=r2(total),
                discount=r2(_f(o.discount_amount)), paid=o.payment_status == "paid", payment_method=o.payment_method,
                net=r2(_f(doc.taxable_amount)) if doc else r2(net_of_igv(total, igv)),
                net_source="document" if doc else "estimated",
                document=f"{doc.series}-{doc.number}" if doc else None,
                customer=full_name(users.get(o.user_id)), pets=pets.get(o.parent_order_id or o.id))

        sales = [sale(o, "service", day_of[o.id]) for o in services]
        paid_adj = [a for a in adjustments if a.payment_status == "paid"]
        sales += [sale(a, "adjustment", day_of[a.parent_order_id]) for a in paid_adj]
        unpaid_adj = [sale(a, "adjustment", day_of[a.parent_order_id]) for a in adjustments
                      if a.payment_status != "paid"]

        movements = [
            MovementFact(id=m.id, code=f"MOV-{m.seq:04d}", day=m.occurred_on, type=m.type, supply=name,
                         quantity=_f(m.quantity), unit_cost=_f(m.unit_cost), order_id=m.order_id, reason=m.reason)
            for m, name in await self.repo.movements(period.start, period.end)
        ]
        supplies_by_order: dict[UUID, float] = {}
        for m in movements:
            if m.type == "consumption" and m.order_id:
                supplies_by_order[m.order_id] = supplies_by_order.get(m.order_id, 0.0) + m.cost

        profiles = await self.cost_repo.list_profiles()
        # Todas las versiones de las recetas del mes en una sola consulta
        self._versions = await self.inventory_repo.recipes_for(list({
            u for o in services for t in order_targets(o.items_snapshot) if (u := _uuid(t.ref_id)) is not None}))
        costs = [await self._cost(o, day_of[o.id], profiles, supplies_by_order.get(o.id, 0.0))
                 for o in services]
        groomers = await self._groomers(period, profiles, services, costs, users)

        cancelled = [
            CancelledPaid(order_id=o.id, day=lima_day(o.updated_at), total=r2(_f(o.total_snapshot)),
                          customer=full_name(users.get(o.user_id)))
            for o in cancelled_orders
        ]
        return build_pnl(
            period=period, igv_percent=igv,
            fee_card_percent=float(fee_card) if fee_card is not None else None,
            fee_yape_percent=float(fee_yape) if fee_yape is not None else None,
            sales=sales, costs=costs, movements=movements, groomers=groomers, cancelled_paid=cancelled,
            unpaid_adjustments=unpaid_adj)

    _versions: dict = field(default_factory=dict, init=False)   # target_id → versiones de su receta

    async def _cost(self, order, day: date, profiles: list, supplies: float) -> ServiceCost:
        rate, source = rates_from_profiles(profiles, day).rate_for(order.groomer_id)
        _, real = order_real_minutes(order)
        targets = order_targets(order.items_snapshot)
        recipes = {}
        for t in targets:
            u = _uuid(t.ref_id)
            chosen = recipe_on(self._versions.get(u, []), order.completed_at or order.updated_at) if u else None
            if chosen is not None:
                recipes[t.ref_id] = chosen
        try:
            plan = await self.consumption.plan_with(order, recipes)
        except Exception:   # una orden que no se puede planear queda sin receta; no tumba el P&L
            logger.exception("pnl: no se pudo planear la orden %s", order.id)
            plan = None
        ok = plan is not None and not plan.missing and bool(plan.cells)
        minutes = plan.labor_minutes if ok else None
        labor = r2(minutes / 60 * rate) if minutes is not None and rate is not None else None
        real_cost = r2(real / 60 * rate) if real is not None and rate is not None else None
        return ServiceCost(
            order_id=order.id, groomer_id=order.groomer_id, supplies=r2(supplies), labor_minutes=minutes,
            labor_rate=r2(rate) if rate is not None else None, labor_rate_source=source if rate is not None else None,
            labor_cost=labor,
            missing=tuple(t.name for t in plan.missing) if plan else tuple(t.name for t in targets),
            recipes=tuple(f"{pc.target.name} {pc.recipe.version_label}" for pc in plan.cells) if plan else (),
            real_minutes=r2(real) if real is not None else None, real_cost=real_cost)

    async def _groomers(self, period, profiles: list, services: list, costs: list[ServiceCost],
                        users: dict) -> list[GroomerMonth]:
        """Costo del mes de cada groomer con registro vigente al corte (activo o con servicios en el mes)."""
        if period.days_elapsed <= 0:
            return []
        by_groomer: dict[UUID, list] = {}
        for p in profiles:
            by_groomer.setdefault(p.groomer_id, []).append(p)
        candidates = {g.id for g in await self.repo.active_groomers()} | {o.groomer_id for o in services if o.groomer_id}
        names = await self.repo.users_by_id([g for g in candidates if g not in users])
        names.update(users)
        out = []
        for gid in candidates:
            profile = profile_on(by_groomer.get(gid, []), period.cut)
            if profile is None:
                continue
            full = profile.monthly_cost
            monthly = full * period.days_elapsed / period.days_in_month if period.is_open else full
            mine = [c for c in costs if c.groomer_id == gid and c.labor_rate_source == "groomer"]
            out.append(GroomerMonth(
                groomer_id=gid, name=full_name(names.get(gid)) or str(gid), monthly_cost=r2(monthly),
                full_monthly_cost=r2(full), assigned=r2(sum(c.labor_cost or 0 for c in mine)),
                services=sum(1 for c in costs if c.groomer_id == gid)))
        return sorted(out, key=lambda g: g.name)


def build_monthly_pnl(session) -> BuildMonthlyPnl:
    """Arma el caso de uso con los repositorios reales."""
    from app.core.db import engine
    from app.modules.finance.infra.postgres_finance_read_repository import PostgresFinanceReadRepository
    from app.modules.general_settings.app.use_cases import get_setting
    from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository
    from app.modules.groomer_costs.infra.postgres_cost_repository import PostgresCostRepository
    from app.modules.inventory.app.use_cases import OrderConsumption
    from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
    from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
    from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

    inventory = PostgresInventoryRepository(session=session)
    settings_repo = PostgresSettingsRepository(session=session)

    async def setting(key: str):
        return await get_setting(settings_repo, key)

    return BuildMonthlyPnl(
        repo=PostgresFinanceReadRepository(session=session),
        inventory_repo=inventory,
        cost_repo=PostgresCostRepository(session=session),
        consumption=OrderConsumption(repo=inventory,
                                     store_repo=PostgresStoreRepository(session=session, engine=engine),
                                     pets_repo=PostgresPetRepository(session=session, engine=engine)),
        settings=setting,
    )
