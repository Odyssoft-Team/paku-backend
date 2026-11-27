"""Cierre mensual / P&L (feature 0024). Solo admin y solo lectura."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.core.timezone import today_lima
from app.modules.finance.api.schemas import (
    CancelledPaidOut,
    ExpenseLineOut,
    GroomerOut,
    LaborComparisonOut,
    LineOut,
    MonthlyPnlOut,
    MovementOut,
    PeriodOut,
    SaleOut,
    ServiceCostOut,
)
from app.modules.finance.app.use_cases import build_monthly_pnl
from app.modules.finance.domain.pnl import MonthlyPnl, month_period, range_period

admin_router = APIRouter(prefix="/finance", tags=["finance-admin"])


def pnl_out(p: MonthlyPnl) -> MonthlyPnlOut:
    period = p.period
    lc = p.labor_comparison
    return MonthlyPnlOut(
        period=PeriodOut(month=period.month, start=period.start, end=period.end, cut=period.cut,
                         is_open=period.is_open, days_in_period=period.days_in_period,
                         days_in_month=period.days_in_month, days_elapsed=period.days_elapsed),
        igv_percent=p.igv_percent, fee_card_percent=p.fee_card_percent, fee_yape_percent=p.fee_yape_percent,
        fee_card_fixed=p.fee_card_fixed, fee_yape_fixed=p.fee_yape_fixed,
        lines=[LineOut(**asdict(ln)) for ln in p.lines],
        sales_with_igv=p.sales_with_igv, discounts=p.discounts, receivable=p.receivable,
        receivable_orders=p.receivable_orders, entry_adjustments=p.entry_adjustments,
        labor_comparison=LaborComparisonOut(services=lc.services, recipe_minutes=lc.recipe_minutes,
                                            real_minutes=lc.real_minutes, recipe_cost=lc.recipe_cost,
                                            real_cost=lc.real_cost, variation=round(lc.variation, 2)),
        cancelled_paid=[CancelledPaidOut(**asdict(c)) for c in p.cancelled_paid],
        sales=[SaleOut(**asdict(s), fee=p.fees.get(s.order_id, 0.0)) for s in p.sales],
        costs=[ServiceCostOut(**{**asdict(c), "missing": list(c.missing), "recipes": list(c.recipes)})
               for c in p.costs],
        movements=[MovementOut(**asdict(m), cost=round(m.cost, 2)) for m in p.movements],
        groomers=[GroomerOut(**asdict(g), unabsorbed=round(g.unabsorbed, 2)) for g in p.groomers],
        expenses=[ExpenseLineOut(**asdict(e)) for e in p.expenses], income_tax_percent=p.income_tax_percent,
    )


@admin_router.get("/pnl", response_model=MonthlyPnlOut)
async def monthly_pnl(
    month: Optional[str] = Query(None, description="AAAA-MM (el mes en curso por defecto).",
                                 pattern=r"^\d{4}-\d{2}$"),
    date_from: Optional[date] = Query(None, description="Rango: primer día (incluido). Va con date_to; gana a month."),
    date_to: Optional[date] = Query(None, description="Rango: último día (incluido). Hoy = date_from = date_to = hoy."),
    _: CurrentUser = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_async_session),
) -> MonthlyPnlOut:
    """
    P&L de un mes o de un rango de días con datos reales: ventas sin IGV (de los comprobantes), costo del servicio
    (insumos, mermas, mano de obra de receta, mano de obra no utilizada y comisión de la pasarela), margen bruto y
    utilidad parcial. Cada línea dice su estado (`real`, `estimated`, `partial`, `not_configured` con importe null) y
    trae el detalle (ventas, costeo por servicio, movimientos y groomers) para rastrear cada importe. La venta va al
    día del servicio realizado. En un rango (o el mes en curso), el costo del groomer se prorratea por los días que
    cubre de cada mes. 422 `PERIOD_INVALID` si el mes o el rango no son válidos (hasta 366 días).
    """
    today = today_lima()
    try:
        if date_from is not None or date_to is not None:
            if date_from is None or date_to is None:
                raise ValueError("Indica la fecha inicial y la final.")
            range_period(date_from, date_to, today)
        else:
            month = month or today.strftime("%Y-%m")
            month_period(month, today)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "PERIOD_INVALID", "message": str(exc)}) from exc
    return pnl_out(await build_monthly_pnl(session).execute(month=month, date_from=date_from, date_to=date_to))
