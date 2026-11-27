"""Cierre mensual / P&L (feature 0024). Solo admin y solo lectura."""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.core.timezone import today_lima
from app.modules.finance.api.schemas import (
    CancelledPaidOut,
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
from app.modules.finance.domain.pnl import MonthlyPnl, month_period

admin_router = APIRouter(prefix="/finance", tags=["finance-admin"])


def pnl_out(p: MonthlyPnl) -> MonthlyPnlOut:
    period = p.period
    lc = p.labor_comparison
    return MonthlyPnlOut(
        period=PeriodOut(month=period.month, start=period.start, end=period.end, cut=period.cut,
                         is_open=period.is_open, days_in_month=period.days_in_month,
                         days_elapsed=period.days_elapsed),
        igv_percent=p.igv_percent, fee_card_percent=p.fee_card_percent, fee_yape_percent=p.fee_yape_percent,
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
    )


@admin_router.get("/pnl", response_model=MonthlyPnlOut)
async def monthly_pnl(
    month: Optional[str] = Query(None, description="AAAA-MM (el mes en curso por defecto).",
                                 pattern=r"^\d{4}-\d{2}$"),
    _: CurrentUser = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_async_session),
) -> MonthlyPnlOut:
    """
    P&L de un mes con datos reales: ventas sin IGV (de los comprobantes), costo del servicio (insumos, mermas, mano
    de obra de receta, mano de obra no utilizada y comisión de la pasarela), margen bruto y utilidad parcial. Cada
    línea dice su estado (`real`, `estimated`, `partial`, `not_configured` con importe null) y trae el detalle
    (ventas, costeo por servicio, movimientos y groomers) para rastrear cada importe. El mes de una venta es el del
    servicio realizado. 422 si el mes no es válido.
    """
    month = month or today_lima().strftime("%Y-%m")
    try:
        month_period(month, today_lima())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "MONTH_INVALID", "message": str(exc)}) from exc
    return pnl_out(await build_monthly_pnl(session).execute(month=month))
