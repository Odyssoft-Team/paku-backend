"""Dashboard gerencial (feature 0014): cifras del mes al día vs. el mismo corte del mes anterior. Solo admin."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.modules.crm.infra.postgres_customer_read_repository import PostgresCustomerReadRepository
from app.modules.dashboard.api.schemas import DashboardOut, DayOutlookOut, MetricOut, PeriodOut
from app.modules.dashboard.app.use_cases import BuildDashboard, order_cost_estimator
from app.modules.dashboard.domain.dashboard import METRICS, delta
from app.modules.dashboard.infra.postgres_dashboard_read_repository import PostgresDashboardReadRepository

admin_router = APIRouter(prefix="/dashboard", tags=["dashboard-admin"])


@admin_router.get("", response_model=DashboardOut)
async def get_dashboard(
    date_: Optional[date] = Query(None, alias="date", description="Día de corte (hoy en Lima por defecto)"),
    _: CurrentUser = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_async_session),
) -> DashboardOut:
    """
    Mes al día (del 1 al corte) comparado con el mismo corte del mes anterior, los servicios que faltan hasta fin
    de mes y los próximos 7 días. Cada cifra dice si es `real`, `estimated` o `no_data` (valor null).
    """
    d = await BuildDashboard(
        repo=PostgresDashboardReadRepository(session=session),
        customers_repo=PostgresCustomerReadRepository(session=session),
        cost_of=order_cost_estimator(session),
    ).execute(cut=date_)
    metrics = []
    for key, (label, unit, description) in METRICS.items():
        cur, prev = d.current[key], d.previous[key]
        diff, pct = delta(cur, prev)
        metrics.append(MetricOut(
            key=key, label=label, unit=unit, description=description, value=cur.value, quality=cur.quality,
            with_data=cur.with_data, total=cur.total, previous=prev.value, previous_quality=prev.quality,
            delta=diff, delta_pct=pct,
        ))
    return DashboardOut(
        cut=d.cut,
        period=PeriodOut(date_from=d.period.date_from, date_to=d.period.date_to),
        previous_period=PeriodOut(date_from=d.previous_period.date_from, date_to=d.previous_period.date_to),
        metrics=metrics,
        scheduled_rest_of_month=d.scheduled_rest_of_month,
        next_days=[
            DayOutlookOut(date=x.day, capacity=x.capacity, booked=x.booked, occupancy_pct=x.occupancy_pct,
                          scheduled=x.scheduled)
            for x in d.next_days
        ],
    )
