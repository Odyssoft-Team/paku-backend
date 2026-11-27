from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

LineStatus = Literal["real", "estimated", "partial", "not_configured"]


class PeriodOut(BaseModel):
    month: Optional[str] = Field(None, description="AAAA-MM si se pidió un mes; null en un rango de fechas.")
    start: date
    end: date
    cut: date = Field(..., description="Último día con datos (hoy si el período está en curso).")
    is_open: bool = Field(..., description="Llega a hoy: lo que se registre después aún lo cambia.")
    days_in_period: int
    days_in_month: Optional[int] = Field(None, description="Solo si se pidió un mes (igual a days_in_period).")
    days_elapsed: int


class LineOut(BaseModel):
    key: str = Field(..., description="net_sales, supplies, shrinkage, labor, unabsorbed_labor, payment_fees, "
                                      "groomer_variable, service_cost, gross_margin, operating_expenses, "
                                      "depreciation, pre_tax_result, taxes, net_result")
    label: str
    amount: Optional[float] = Field(None, description="S/. null = no configurado (nunca 0 inventado).")
    status: LineStatus
    section: Literal["sales", "cost", "margin", "expense", "result"]
    note: Optional[str] = None
    count: Optional[int] = Field(None, description="Cuántos registros forman la línea.")


class SaleOut(BaseModel):
    order_id: UUID
    kind: Literal["service", "adjustment"]
    parent_order_id: Optional[UUID] = None
    day: date = Field(..., description="Día del servicio (Lima).")
    total: float = Field(..., description="Con IGV.")
    discount: float
    paid: bool
    payment_method: Optional[str] = None
    net: float = Field(..., description="Sin IGV.")
    net_source: Literal["document", "estimated"] = Field(
        ..., description="document = la del comprobante; estimated = total ÷ (1 + IGV), pendiente de boleta.")
    document: Optional[str] = None
    customer: Optional[str] = None
    pets: Optional[str] = None
    fee: float = Field(0, description="Comisión de la pasarela de esta orden.")


class ServiceCostOut(BaseModel):
    order_id: UUID
    groomer_id: Optional[UUID] = None
    supplies: float
    labor_minutes: Optional[float] = Field(None, description="Minutos de receta; null si falta receta.")
    labor_rate: Optional[float] = None
    labor_rate_source: Optional[Literal["groomer", "reference"]] = None
    labor_cost: Optional[float] = None
    missing: list[str] = Field(default_factory=list, description="Servicio o adicionales sin receta.")
    recipes: list[str] = Field(default_factory=list, description="Versión de receta usada: «Baño R2».")
    real_minutes: Optional[float] = Field(None, description="Llegada → fin.")
    real_cost: Optional[float] = None


class MovementOut(BaseModel):
    id: UUID
    code: str
    day: date
    type: Literal["consumption", "waste", "adjustment"]
    supply: str
    quantity: float
    unit_cost: float
    cost: float = Field(..., description="Salida positiva; una entrada (ajuste) da negativo.")
    order_id: Optional[UUID] = None
    reason: str


class GroomerOut(BaseModel):
    groomer_id: UUID
    name: str
    monthly_cost: float = Field(..., description="Del mes (prorrateado a los días transcurridos si está abierto).")
    full_monthly_cost: float
    assigned: float = Field(..., description="Mano de obra de receta de sus servicios del mes.")
    unabsorbed: float = Field(..., description="monthly_cost − assigned (negativo: trabajó más de lo pagado).")
    services: int


class LaborComparisonOut(BaseModel):
    services: int = Field(..., description="Servicios con receta y tiempo real registrado.")
    recipe_minutes: float
    real_minutes: float
    recipe_cost: float
    real_cost: float
    variation: float = Field(..., description="Real − receta: positivo = costó más de lo estimado.")


class ExpenseLineOut(BaseModel):
    expense_id: UUID
    kind: str
    category: str
    category_label: str
    description: str
    start_date: date
    vehicle: Optional[str] = None
    amount: float = Field(..., description="Sin IGV: total (único / anual) o por mes (mensual).")
    in_period: float = Field(..., description="Lo que aporta al período.")


class CancelledPaidOut(BaseModel):
    order_id: UUID
    day: date
    total: float
    customer: Optional[str] = None


class MonthlyPnlOut(BaseModel):
    period: PeriodOut
    igv_percent: float
    fee_card_percent: Optional[float] = None
    fee_yape_percent: Optional[float] = None
    fee_card_fixed: float = Field(0, description="S/ por cobro con tarjeta.")
    fee_yape_fixed: float = Field(0, description="S/ por cobro con Yape.")
    lines: list[LineOut]
    sales_with_igv: float
    discounts: float = Field(..., description="Descuentos de campaña (ya restados en las ventas).")
    receivable: float = Field(..., description="Servicios del mes y ajustes sin pagar.")
    receivable_orders: list[UUID]
    entry_adjustments: float = Field(..., description="Ajustes de entrada del mes: informativo, no restan.")
    labor_comparison: LaborComparisonOut
    cancelled_paid: list[CancelledPaidOut] = Field(
        ..., description="Pagadas y canceladas en el mes: pendientes de reprogramar o reembolsar (no son venta).")
    sales: list[SaleOut]
    costs: list[ServiceCostOut]
    movements: list[MovementOut]
    groomers: list[GroomerOut]
    expenses: list[ExpenseLineOut] = Field(default_factory=list, description="Gastos operativos del período.")
    income_tax_percent: Optional[float] = None
