"""Dashboard gerencial (feature 0014): arma las cifras del mes al día y del mismo corte del mes anterior."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from app.core.timezone import today_lima
from app.modules.dashboard.domain.dashboard import (
    NEXT_DAYS,
    DayOutlook,
    Figure,
    Period,
    ServiceFact,
    lima_bounds,
    lima_day,
    month_end,
    month_to_date,
    outlook,
    period_figures,
)
from app.modules.inventory.app.use_cases import order_real_minutes

logger = logging.getLogger(__name__)

CostFn = Callable[[Any], Awaitable[Optional[float]]]


def service_day(order) -> date:
    """Día (en Lima) del servicio: cuando terminó; si no hay, el programado o la creación (como Clientes)."""
    return lima_day(order.completed_at or order.scheduled_at or order.created_at)


def _arrival(order) -> Optional[datetime]:
    for e in order.service_steps_log or []:
        if isinstance(e, dict) and e.get("step") == "reception" and e.get("started_at"):
            value = e["started_at"]
            return datetime.fromisoformat(value) if isinstance(value, str) else value
    return None


def arrival_offset_minutes(order) -> Optional[float]:
    """Llegada − hora programada, en minutos (negativo = llegó antes). None si falta alguna."""
    arrival, scheduled = _arrival(order), order.scheduled_at
    if arrival is None or scheduled is None:
        return None
    arrival, scheduled = (t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in (arrival, scheduled))  # BD en UTC
    return round((arrival - scheduled).total_seconds() / 60, 1)


@dataclass(frozen=True)
class Dashboard:
    cut: date
    period: Period
    previous_period: Period
    current: dict[str, Figure]
    previous: dict[str, Figure]
    scheduled_rest_of_month: int
    next_days: list[DayOutlook]


@dataclass
class BuildDashboard:
    repo: Any              # PostgresDashboardReadRepository
    customers_repo: Any    # crm: órdenes terminadas + cargos extra pagados
    cost_of: CostFn        # costo estimado de una orden (insumos + mano de obra) o None

    async def execute(self, *, cut: Optional[date] = None) -> Dashboard:
        cut = cut or today_lima()
        current, previous = month_to_date(cut)
        span = Period(previous.date_from, current.date_to)

        orders = await self.customers_repo.service_orders()
        extra: dict[UUID, float] = {}
        for o in orders:
            if o.parent_order_id is not None:  # cargo extra pagado
                extra[o.parent_order_id] = extra.get(o.parent_order_id, 0.0) + float(o.total_snapshot)

        first_visit: dict[UUID, date] = {}
        services: list[ServiceFact] = []
        for o in orders:
            if o.parent_order_id is not None:
                continue
            day = service_day(o)
            if o.user_id not in first_visit or day < first_visit[o.user_id]:
                first_visit[o.user_id] = day
            if day not in current and day not in previous:
                continue
            total = float(o.total_snapshot)
            travel, service = order_real_minutes(o)
            services.append(ServiceFact(
                order_id=o.id, user_id=o.user_id, day=day, revenue=round(total + extra.get(o.id, 0.0), 2),
                unpaid=0.0 if o.payment_status.value == "paid" else total, cost=await self.cost_of(o),
                travel_minutes=travel, service_minutes=service, arrival_offset_minutes=arrival_offset_minutes(o),
            ))

        start, end = lima_bounds(span)
        cancelled = [lima_day(o.updated_at) for o in await self.repo.cancelled_orders(start, end)]
        delays = [lima_day(t) for t in await self.repo.delay_report_times(start, end)]
        last_day = cut + timedelta(days=NEXT_DAYS - 1)
        slots = await self.repo.slots(span.date_from, max(current.date_to, last_day))

        scheduled_days = [
            d for d in (o.reserved_date or lima_day(o.scheduled_at) for o in await self.repo.requested_orders())
            if d is not None
        ]
        rest = Period(cut, month_end(cut))

        def figures(period: Period) -> dict[str, Figure]:
            return period_figures(period, services=services, first_visit=first_visit, cancellation_days=cancelled,
                                  slots=slots, delay_report_days=delays)

        return Dashboard(
            cut=cut, period=current, previous_period=previous, current=figures(current), previous=figures(previous),
            scheduled_rest_of_month=sum(1 for d in scheduled_days if d in rest),
            next_days=outlook(Period(cut, last_day).days(), slots=slots, scheduled_days=scheduled_days),
        )


def order_cost_estimator(session) -> CostFn:
    """Costo estimado de una orden con el costeo de Inventario (feature 0009/0012): insumos registrados o de la
    receta + minutos de receta × costo por hora. None si falta receta (servicio o algún adicional) o tarifa."""
    from app.core.db import engine
    from app.modules.inventory.app.use_cases import GetOrderCost, order_labor_rates
    from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
    from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
    from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

    costing = GetOrderCost(
        repo=PostgresInventoryRepository(session=session),
        store_repo=PostgresStoreRepository(session=session, engine=engine),
        pets_repo=PostgresPetRepository(session=session, engine=engine),
    )
    rates_by_day: dict[date, Any] = {}

    async def cost_of(order) -> Optional[float]:
        day = lima_day(order.completed_at or order.updated_at)  # el mismo día que usa order_labor_rates
        if day not in rates_by_day:
            rates_by_day[day] = await order_labor_rates(session, order)
        try:
            cost = await costing.execute(order, rates=rates_by_day[day])
        except Exception:  # una orden que no se puede costear queda "sin datos"; no tumba el dashboard
            logger.exception("dashboard: no se pudo costear la orden %s", order.id)
            try:
                await session.rollback()  # si falló una consulta, la sesión debe seguir sirviendo
            except Exception:
                pass
            return None
        if cost.plan.missing or not cost.plan.cells or cost.labor_cost_estimated is None:
            return None
        return round(cost.supplies_cost + cost.labor_cost_estimated, 2)

    return cost_of
