"""Cierre mensual / P&L (feature 0024, etapa 1): reglas puras, sin base de datos.

- El mes de una venta es el del servicio realizado (día de término en Lima); sus costos van al mismo mes.
- Venta sin IGV: la del comprobante vigente; sin comprobante, total ÷ (1 + IGV) y queda «pendiente de boleta».
- Costo del servicio: insumos consumidos, mermas y ajustes de salida, mano de obra de la receta (versión vigente el
  día del servicio), mano de obra no utilizada (costo mensual del groomer − asignado) y comisión de la pasarela.
- Lo que aún no se registra (variable del groomer, gastos, depreciación, impuestos) sale «no configurado», nunca 0.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Optional
from uuid import UUID

# Estado de cada cifra
REAL = "real"                      # sale directo de los registros
ESTIMATED = "estimated"            # usa recetas, tarifas o porcentajes
PARTIAL = "partial"                # faltan datos de una parte (dice cuántos)
NOT_CONFIGURED = "not_configured"  # no se registra todavía: el importe va vacío


def r2(x: float) -> float:
    return round(x + 0.0, 2)


MAX_RANGE_DAYS = 366


@dataclass(frozen=True)
class Period:
    """Un mes (`month`) o un rango de días cualquiera (`month` None), ambos extremos incluidos."""
    start: date
    end: date
    cut: date           # último día con datos: hoy si el período está en curso
    is_open: bool       # llega a hoy (o al futuro): lo que pase después aún lo cambia
    month: Optional[str] = None   # YYYY-MM si el período es un mes calendario

    @property
    def days_in_period(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def days_in_month(self) -> Optional[int]:
        return self.days_in_period if self.month else None

    @property
    def days_elapsed(self) -> int:
        return max(0, (self.cut - self.start).days + 1)

    @property
    def is_full_month(self) -> bool:
        """Mes calendario completo y cerrado: el costo del groomer va entero, sin prorrateo."""
        return self.month is not None and not self.is_open

    def month_segments(self) -> list[tuple[date, date, int]]:
        """Tramos por mes calendario de los días transcurridos (inicio → corte): (desde, hasta, días del mes)."""
        out = []
        day = self.start
        while day <= self.cut:
            last = date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
            until = min(last, self.cut)
            out.append((day, until, last.day))
            day = date.fromordinal(until.toordinal() + 1)
        return out

    def __contains__(self, day: Optional[date]) -> bool:
        return day is not None and self.start <= day <= self.end


def _with_cut(start: date, end: date, today: date, month: Optional[str] = None) -> Period:
    # Período futuro: el corte queda antes del inicio (sin días transcurridos)
    cut = min(end, today) if start <= today else date.fromordinal(start.toordinal() - 1)
    return Period(start=start, end=end, cut=cut, is_open=end >= today, month=month)


def month_period(month: str, today: date) -> Period:
    """`YYYY-MM` → período. ValueError si no es un mes válido."""
    try:
        year, mon = (int(p) for p in month.split("-"))
        start = date(year, mon, 1)
    except (ValueError, TypeError) as exc:
        raise ValueError("El mes va como AAAA-MM.") from exc
    end = date(year, mon, calendar.monthrange(year, mon)[1])
    return _with_cut(start, end, today, month=f"{year:04d}-{mon:02d}")


def range_period(date_from: date, date_to: date, today: date) -> Period:
    """Rango de días (ambos incluidos; un solo día = «hoy» u otro día). ValueError si no es válido."""
    if date_from > date_to:
        raise ValueError("La fecha inicial debe ser anterior o igual a la final.")
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise ValueError(f"El rango admite hasta {MAX_RANGE_DAYS} días.")
    return _with_cut(date_from, date_to, today)


def net_of_igv(total: float, igv_percent: float) -> float:
    """Valor de venta sin IGV de un total con IGV (los precios de Paku incluyen IGV)."""
    return total / (1 + (igv_percent or 0) / 100)


def recipe_on(versions: list, when: Optional[datetime]):
    """Versión de la receta que regía en `when`: la última creada hasta ese momento. Si el servicio es anterior a la
    primera versión, la primera (supuesto del spec 0024). None sin versiones."""
    if not versions:
        return None
    ordered = sorted(versions, key=lambda r: r.version)
    if when is None:
        return ordered[-1]
    valid = [r for r in ordered if _aware(r.created_at) <= _aware(when)]
    return valid[-1] if valid else ordered[0]


def _aware(dt: datetime) -> datetime:
    from datetime import timezone

    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# ---------- Hechos ----------

@dataclass(frozen=True)
class SaleFact:
    """Una orden que vende en el mes: un servicio realizado o un ajuste por peso de ese servicio."""
    order_id: UUID
    kind: str                         # service | adjustment
    parent_order_id: Optional[UUID]
    day: date                         # día del servicio (el del servicio original en un ajuste)
    total: float                      # con IGV (lo cobrado o por cobrar)
    discount: float                   # descuento de campaña, ya restado en el total
    paid: bool
    payment_method: Optional[str]     # card | yape | cash
    net: float                        # sin IGV
    net_source: str                   # document | estimated
    document: Optional[str] = None    # B001-123
    customer: Optional[str] = None
    pets: Optional[str] = None


@dataclass(frozen=True)
class ServiceCost:
    """Costeo de un servicio realizado del mes."""
    order_id: UUID
    groomer_id: Optional[UUID]
    supplies: float                   # insumos registrados de la orden (movimientos del mes)
    labor_minutes: Optional[float]    # minutos de receta; None si falta receta (base o adicional)
    labor_rate: Optional[float]       # S/ por hora de servicio
    labor_rate_source: Optional[str]  # groomer | reference
    labor_cost: Optional[float]       # None sin receta o sin tarifa
    missing: tuple[str, ...] = ()     # servicios o adicionales sin receta
    recipes: tuple[str, ...] = ()     # «Baño R2», para rastrear la versión usada
    real_minutes: Optional[float] = None
    real_cost: Optional[float] = None


@dataclass(frozen=True)
class MovementFact:
    id: UUID
    code: str                         # MOV-0001
    day: date
    type: str                         # consumption | waste | adjustment
    supply: str
    quantity: float                   # con signo
    unit_cost: float
    order_id: Optional[UUID]
    reason: str

    @property
    def cost(self) -> float:
        """Costo de una salida (positivo); una entrada da negativo."""
        return -self.quantity * self.unit_cost


@dataclass(frozen=True)
class GroomerMonth:
    groomer_id: UUID
    name: str
    monthly_cost: float               # costo del período: el mensual de cada mes × días cubiertos ÷ días del mes
    full_monthly_cost: float          # costo mensual del registro vigente al corte
    assigned: float                   # mano de obra de receta de sus servicios del mes
    services: int

    @property
    def unabsorbed(self) -> float:
        return self.monthly_cost - self.assigned


@dataclass(frozen=True)
class CancelledPaid:
    order_id: UUID
    day: date
    total: float
    customer: Optional[str] = None


# ---------- Resultado ----------

@dataclass(frozen=True)
class Line:
    key: str
    label: str
    amount: Optional[float]           # None = no configurado / sin datos
    status: str
    section: str                      # sales | cost | margin | expense | result
    note: Optional[str] = None
    count: Optional[int] = None


@dataclass(frozen=True)
class LaborComparison:
    services: int                     # con receta y tiempo real
    recipe_cost: float
    real_cost: float
    recipe_minutes: float
    real_minutes: float

    @property
    def variation(self) -> float:
        """Real − receta: positivo = el tiempo real costó más (pérdida); negativo = ahorro."""
        return self.real_cost - self.recipe_cost


@dataclass(frozen=True)
class MonthlyPnl:
    period: Period
    igv_percent: float
    fee_card_percent: Optional[float]
    fee_yape_percent: Optional[float]
    lines: list[Line]
    sales: list[SaleFact]
    costs: list[ServiceCost]
    movements: list[MovementFact]
    groomers: list[GroomerMonth]
    labor_comparison: LaborComparison
    receivable: float
    receivable_orders: list[UUID]
    cancelled_paid: list[CancelledPaid]
    discounts: float
    sales_with_igv: float
    entry_adjustments: float          # ajustes de entrada del mes (informativo, no restan)
    fees: dict[UUID, float] = field(default_factory=dict)   # comisión por orden


def _sum(xs: Iterable[float]) -> float:
    return r2(sum(xs))


def fee_for(sale: SaleFact, card: Optional[float], yape: Optional[float]) -> tuple[Optional[float], bool]:
    """(comisión, configurada). Solo lo cobrado con tarjeta o Yape; el efectivo no paga comisión."""
    if not sale.paid or sale.payment_method not in ("card", "yape"):
        return 0.0, True
    pct = card if sale.payment_method == "card" else yape
    if pct is None:
        return None, False
    return sale.total * pct / 100, True


def build_pnl(
    *,
    period: Period,
    igv_percent: float,
    fee_card_percent: Optional[float],
    fee_yape_percent: Optional[float],
    sales: list[SaleFact],
    costs: list[ServiceCost],
    movements: list[MovementFact],
    groomers: list[GroomerMonth],
    cancelled_paid: list[CancelledPaid],
    unpaid_adjustments: Iterable[SaleFact] = (),
) -> MonthlyPnl:
    """`sales`: servicios realizados del mes y sus ajustes pagados. `unpaid_adjustments`: ajustes sin pagar de esos
    servicios (no son venta todavía; van a «por cobrar»)."""
    services = [s for s in sales if s.kind == "service"]
    lines: list[Line] = []

    # Ventas
    pending_docs = sum(1 for s in sales if s.net_source != "document")
    net_sales = _sum(s.net for s in sales)
    lines.append(Line(
        "net_sales", "Ventas sin IGV", net_sales, ESTIMATED if pending_docs else REAL, "sales",
        note=(f"{pending_docs} de {len(sales)} sin boleta: calculadas con IGV {igv_percent:g} %"
              if pending_docs else f"{len(services)} servicios realizados"),
        count=len(sales)))

    # Costo del servicio
    consumption = [m for m in movements if m.type == "consumption"]
    shrink = [m for m in movements if m.type == "waste" or (m.type == "adjustment" and m.quantity < 0)]
    entries = [m for m in movements if m.type == "adjustment" and m.quantity > 0]
    lines.append(Line("supplies", "Insumos consumidos", _sum(m.cost for m in consumption), REAL, "cost",
                      count=len(consumption)))
    lines.append(Line("shrinkage", "Mermas y diferencias de inventario", _sum(m.cost for m in shrink), REAL, "cost",
                      count=len(shrink)))

    with_labor = [c for c in costs if c.labor_cost is not None]
    labor = _sum(c.labor_cost for c in with_labor)
    no_recipe = len(costs) - len(with_labor)
    lines.append(Line(
        "labor", "Mano de obra (receta)", labor, PARTIAL if no_recipe else ESTIMATED, "cost",
        note=(f"{no_recipe} de {len(costs)} servicios sin receta o sin costo por hora: no suman" if no_recipe
              else "Minutos de la receta vigente el día del servicio × costo por hora del groomer"),
        count=len(with_labor)))

    if groomers:
        unabsorbed = _sum(g.unabsorbed for g in groomers)
        lines.append(Line(
            "unabsorbed_labor", "Mano de obra no utilizada", unabsorbed, ESTIMATED, "cost",
            note=("Costo mensual del groomer − lo asignado a servicios" if period.is_full_month
                  else "Costo del groomer prorrateado a los días del período − lo asignado a servicios"),
            count=len(groomers)))
    else:
        lines.append(Line("unabsorbed_labor", "Mano de obra no utilizada", None, NOT_CONFIGURED, "cost",
                          note="Sin costo del groomer registrado (Groomers → Costo)"))

    fees: dict[UUID, float] = {}
    missing_fee = 0
    for s in sales:
        amount, ok = fee_for(s, fee_card_percent, fee_yape_percent)
        if not ok:
            missing_fee += 1
        elif amount:
            fees[s.order_id] = r2(amount)
    if missing_fee:
        lines.append(Line("payment_fees", "Comisión de la pasarela", _sum(fees.values()) if fees else None,
                          PARTIAL if fees else NOT_CONFIGURED, "cost",
                          note=f"Falta el % de comisión (Parámetros generales → Finanzas) para {missing_fee} cobros",
                          count=len(fees)))
    else:
        lines.append(Line("payment_fees", "Comisión de la pasarela", _sum(fees.values()), ESTIMATED, "cost",
                          note="Total cobrado con tarjeta o Yape × % de Parámetros generales", count=len(fees)))

    lines.append(Line("groomer_variable", "Variable del groomer", None, NOT_CONFIGURED, "cost",
                      note="Se define en una etapa siguiente (puntos por servicio, adicional y eficiencia)"))

    cost_lines = [ln for ln in lines if ln.section == "cost"]
    cost_total = _sum(ln.amount for ln in cost_lines if ln.amount is not None)
    incomplete = any(ln.status in (PARTIAL, NOT_CONFIGURED) for ln in cost_lines)
    lines.append(Line("service_cost", "Costo del servicio", cost_total, PARTIAL if incomplete else ESTIMATED,
                      "margin"))
    gross = r2(net_sales - cost_total)
    lines.append(Line("gross_margin", "Margen bruto", gross, PARTIAL if incomplete else ESTIMATED, "margin",
                      note=f"{gross / net_sales * 100:.1f} % de las ventas" if net_sales else None))

    for key, label in (("operating_expenses", "Gastos operativos"), ("depreciation", "Depreciación"),
                       ("taxes", "Impuestos")):
        lines.append(Line(key, label, None, NOT_CONFIGURED, "expense", note="No se registra todavía"))
    lines.append(Line("net_result", "Utilidad", gross, PARTIAL, "result",
                      note="Parcial: faltan gastos operativos, depreciación e impuestos"))

    compared =[c for c in costs if c.labor_cost is not None and c.real_cost is not None]
    comparison = LaborComparison(
        services=len(compared),
        recipe_cost=_sum(c.labor_cost for c in compared),
        real_cost=_sum(c.real_cost for c in compared),
        recipe_minutes=r2(sum(c.labor_minutes or 0 for c in compared)),
        real_minutes=r2(sum(c.real_minutes or 0 for c in compared)),
    )
    unpaid = [s for s in sales if not s.paid] + list(unpaid_adjustments)
    return MonthlyPnl(
        period=period, igv_percent=igv_percent, fee_card_percent=fee_card_percent, fee_yape_percent=fee_yape_percent,
        lines=lines, sales=sales, costs=costs, movements=movements, groomers=groomers, labor_comparison=comparison,
        receivable=_sum(s.total for s in unpaid), receivable_orders=[s.order_id for s in unpaid],
        cancelled_paid=cancelled_paid, discounts=_sum(s.discount for s in sales),
        sales_with_igv=_sum(s.total for s in sales), entry_adjustments=_sum(-m.cost for m in entries), fees=fees,
    )
