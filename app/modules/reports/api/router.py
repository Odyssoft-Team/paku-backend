"""Reporte de ventas (feature 0016): servicios vendidos con filtros, totales y resúmenes. Solo admin."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.modules.orders.domain.order import OrderStatus, PaymentMethod, PaymentStatus
from app.modules.reports.app.use_cases import BuildSalesReport
from app.modules.reports.domain.sales import SalesFilters
from app.modules.reports.infra.postgres_sales_read_repository import PostgresSalesReadRepository

admin_router = APIRouter(prefix="/reports", tags=["reports-admin"])


class SaleRowOut(BaseModel):
    order_id: UUID
    purchase_date: date
    service_date: Optional[date] = None
    order_status: str
    payment_status: str
    payment_method: Optional[str] = None
    customer_id: UUID
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None
    pet_name: Optional[str] = None
    service_id: Optional[str] = None
    service_name: str
    addon_names: list[str]
    subtotal: float = Field(description="Suma de los ítems")
    discount: float = Field(description="Descuento de campaña")
    total: float = Field(description="Neto de la orden (total_snapshot)")
    extra_paid: float = Field(description="Cargos extra pagados")
    collected: float = Field(description="Neto si está pagada + cargos extra pagados")
    groomer_id: Optional[UUID] = None
    groomer_name: Optional[str] = None
    district_id: Optional[str] = None
    district_name: Optional[str] = None
    campaign_id: Optional[UUID] = None
    campaign_name: Optional[str] = None


class SalesTotalsOut(BaseModel):
    orders: int
    subtotal: float
    discount: float
    total: float
    extra_paid: float
    collected: float
    avg_ticket: Optional[float] = Field(default=None, description="Cobrado ÷ órdenes pagadas")
    cancelled: int


class GroupTotalOut(BaseModel):
    key: Optional[str] = None
    label: str
    orders: int
    total: float
    collected: float


class OptionOut(BaseModel):
    value: str
    label: str


class SalesOptionsOut(BaseModel):
    services: list[OptionOut]
    groomers: list[OptionOut]
    districts: list[OptionOut]
    campaigns: list[OptionOut]


class SalesReportOut(BaseModel):
    rows: list[SaleRowOut]
    totals: SalesTotalsOut
    by_service: list[GroupTotalOut]
    by_payment_method: list[GroupTotalOut]
    by_order_status: list[GroupTotalOut]
    options: SalesOptionsOut = Field(description="Valores presentes en el rango de fechas, para los filtros")


@admin_router.get("/sales", response_model=SalesReportOut)
async def sales_report(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    date_basis: str = Query("purchase", description="purchase (fecha de compra) | service (fecha del servicio)"),
    order_status: Optional[OrderStatus] = Query(None),
    payment_status: Optional[PaymentStatus] = Query(None),
    payment_method: Optional[PaymentMethod] = Query(None),
    service_id: Optional[str] = Query(None, description="Servicio base (producto)"),
    groomer_id: Optional[UUID] = Query(None),
    district_id: Optional[str] = Query(None),
    campaign_id: Optional[UUID] = Query(None),
    q: Optional[str] = Query(None, description="Cliente (nombre, correo, teléfono), mascota o n.º de orden"),
    _: CurrentUser = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_async_session),
) -> SalesReportOut:
    """
    Servicios vendidos: una fila por orden de servicio, con sus cargos extra pagados. Fechas en hora de Lima.
    Sin filtros de estado trae todas (también las sin pagar o canceladas); filtra `payment_status=paid` para ventas
    cobradas.
    """
    report = await BuildSalesReport(repo=PostgresSalesReadRepository(session=session)).execute(SalesFilters(
        date_from=date_from, date_to=date_to, date_basis=date_basis,
        order_status=order_status.value if order_status else None,
        payment_status=payment_status.value if payment_status else None,
        payment_method=payment_method.value if payment_method else None,
        service_id=service_id, groomer_id=groomer_id, district_id=district_id, campaign_id=campaign_id, q=q,
    ))
    return SalesReportOut(
        rows=[SaleRowOut(**r.__dict__) for r in report.rows],
        totals=SalesTotalsOut(**report.totals.__dict__),
        by_service=[GroupTotalOut(**g.__dict__) for g in report.by_service],
        by_payment_method=[GroupTotalOut(**g.__dict__) for g in report.by_payment_method],
        by_order_status=[GroupTotalOut(**g.__dict__) for g in report.by_order_status],
        options=SalesOptionsOut(**{k: [OptionOut(value=v, label=l) for v, l in items]
                                   for k, items in report.options.items()}),
    )
