"""Dashboard gerencial (feature 0014): cifras del mes al día comparadas con el mismo corte del mes anterior.

Todo sale de reglas que ya existen (órdenes, cupos, tiempos, clientes y costeo por orden). Cada cifra trae su
calidad: `real` (de los registros), `estimated` (usa recetas y tarifas) o `no_data` (no hay qué medir: el valor
va vacío, nunca 0).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from uuid import UUID

from app.core.timezone import LIMA_TZ

REAL, ESTIMATED, NO_DATA = "real", "estimated", "no_data"
NEXT_DAYS = 7

# key → (etiqueta, unidad, cómo se calcula). Unidades: count | money | pct | minutes.
METRICS: dict[str, tuple[str, str, str]] = {
    "services_done": ("Servicios realizados", "count", "Órdenes de servicio terminadas, por el día del servicio."),
    "revenue": ("Ingresos por servicios realizados", "money",
                "Total neto de cada servicio realizado (con descuento) más sus cargos extra pagados."),
    "avg_ticket": ("Ticket promedio", "money", "Ingresos ÷ servicios realizados."),
    "receivable": ("Por cobrar", "money", "Servicios realizados cuya orden no está pagada."),
    "cancellations": ("Cancelaciones", "count", "Reservas pagadas o en verificación que se cancelaron."),
    "occupancy": ("Ocupación", "pct", "Cupos tomados ÷ capacidad de los días con cupos (incluye carritos vigentes)."),
    "new_customers": ("Clientes nuevos", "count", "Su primer servicio realizado cae en el período."),
    "returning_customers": ("Clientes con recompra", "count",
                            "Tuvieron un servicio en el período y otro antes del período."),
    "contribution": ("Contribución estimada", "money",
                     "Ingreso − insumos − mano de obra estimada (receta × costo por hora). "
                     "Solo órdenes con receta y costo por hora."),
    "contribution_pct": ("Margen de contribución", "pct", "Contribución ÷ ingreso de las órdenes estimadas."),
    "avg_travel_minutes": ("Traslado promedio", "minutes", "Salida → llegada."),
    "avg_service_minutes": ("Atención promedio", "minutes", "Llegada → fin del servicio."),
    "avg_arrival_offset_minutes": ("Llegada vs. hora programada", "minutes",
                                   "Promedio de llegada − hora programada (negativo = antes)."),
    "delay_reports": ("Avisos de retraso", "count", "Retrasos que reportó el groomer."),
}


@dataclass(frozen=True)
class Period:
    date_from: date
    date_to: date

    def __contains__(self, day: Optional[date]) -> bool:
        return day is not None and self.date_from <= day <= self.date_to

    def days(self) -> list[date]:
        return [self.date_from + timedelta(days=i) for i in range((self.date_to - self.date_from).days + 1)]


def month_to_date(cut: date) -> tuple[Period, Period]:
    """Mes al día y el mismo corte del mes anterior (si ese mes es más corto, hasta su último día)."""
    prev_month_last = cut.replace(day=1) - timedelta(days=1)
    prev_cut = prev_month_last.replace(day=min(cut.day, prev_month_last.day))
    return Period(cut.replace(day=1), cut), Period(prev_cut.replace(day=1), prev_cut)


def month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def lima_day(when) -> Optional[date]:
    if when is None:
        return None
    if isinstance(when, str):
        when = datetime.fromisoformat(when)
    if when.tzinfo is None:  # la BD guarda en UTC
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(LIMA_TZ).date()


def lima_bounds(period: Period) -> tuple[datetime, datetime]:
    """[inicio, fin) del período en hora de Lima, en UTC (como guarda la BD), para filtrar timestamps."""
    start = datetime.combine(period.date_from, datetime.min.time(), tzinfo=LIMA_TZ)
    end = datetime.combine(period.date_to + timedelta(days=1), datetime.min.time(), tzinfo=LIMA_TZ)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


@dataclass(frozen=True)
class ServiceFact:
    """Un servicio realizado, ya reducido a lo que mide el dashboard."""
    order_id: UUID
    user_id: UUID
    day: date
    revenue: float                         # total neto + cargos extra pagados
    unpaid: float                          # total neto si la orden no está pagada
    cost: Optional[float]                  # insumos + mano de obra estimada; None = sin datos
    travel_minutes: Optional[float] = None
    service_minutes: Optional[float] = None
    arrival_offset_minutes: Optional[float] = None


@dataclass(frozen=True)
class SlotDay:
    day: date
    capacity: int
    booked: int


@dataclass(frozen=True)
class Figure:
    value: Optional[float]
    quality: str
    with_data: Optional[int] = None        # órdenes que se pudieron medir/estimar…
    total: Optional[int] = None            # …de cuántas


def _real(value: float) -> Figure:
    return Figure(round(value, 2), REAL)


def _avg(values: list[Optional[float]], total: int) -> Figure:
    known = [v for v in values if v is not None]
    if not known:
        return Figure(None, NO_DATA, 0, total)
    return Figure(round(sum(known) / len(known), 1), REAL, len(known), total)


def period_figures(
    period: Period,
    *,
    services: Iterable[ServiceFact],
    first_visit: dict[UUID, date],
    cancellation_days: Iterable[date],
    slots: Iterable[SlotDay],
    delay_report_days: Iterable[date],
) -> dict[str, Figure]:
    done = [s for s in services if s.day in period]
    revenue = sum(s.revenue for s in done)
    costed = [s for s in done if s.cost is not None]
    costed_revenue = sum(s.revenue for s in costed)
    contribution = sum(s.revenue - s.cost for s in costed)
    in_period = [s for s in slots if s.day in period]
    capacity = sum(s.capacity for s in in_period)
    users = {s.user_id for s in done}
    figures = {
        "services_done": _real(len(done)),
        "revenue": _real(revenue),
        "avg_ticket": _real(revenue / len(done)) if done else Figure(None, NO_DATA),
        "receivable": _real(sum(s.unpaid for s in done)),
        "cancellations": _real(sum(1 for d in cancellation_days if d in period)),
        "occupancy": (_real(sum(s.booked for s in in_period) / capacity * 100) if capacity
                      else Figure(None, NO_DATA)),
        "new_customers": _real(sum(1 for u in users if first_visit.get(u) in period)),
        "returning_customers": _real(sum(1 for u in users if first_visit.get(u) and first_visit[u] < period.date_from)),
        "contribution": (Figure(round(contribution, 2), ESTIMATED, len(costed), len(done)) if costed
                         else Figure(None, NO_DATA, 0, len(done))),
        "contribution_pct": (Figure(round(contribution / costed_revenue * 100, 1), ESTIMATED, len(costed), len(done))
                             if costed and costed_revenue else Figure(None, NO_DATA, 0, len(done))),
        "avg_travel_minutes": _avg([s.travel_minutes for s in done], len(done)),
        "avg_service_minutes": _avg([s.service_minutes for s in done], len(done)),
        "avg_arrival_offset_minutes": _avg([s.arrival_offset_minutes for s in done], len(done)),
        "delay_reports": _real(sum(1 for d in delay_report_days if d in period)),
    }
    return figures


def delta(current: Figure, previous: Figure) -> tuple[Optional[float], Optional[float]]:
    """(diferencia, diferencia %) entre el período y el anterior; None si alguno no tiene datos."""
    if current.value is None or previous.value is None:
        return None, None
    diff = round(current.value - previous.value, 2)
    pct = round(diff / abs(previous.value) * 100, 1) if previous.value else None
    return diff, pct


@dataclass(frozen=True)
class DayOutlook:
    day: date
    capacity: Optional[int]                # None: el día no tiene cupos
    booked: Optional[int]
    occupancy_pct: Optional[float]
    scheduled: int                         # servicios solicitados para ese día


def outlook(days: list[date], *, slots: Iterable[SlotDay], scheduled_days: list[date]) -> list[DayOutlook]:
    by_day: dict[date, tuple[int, int]] = {}
    for s in slots:
        cap, booked = by_day.get(s.day, (0, 0))
        by_day[s.day] = (cap + s.capacity, booked + s.booked)
    out = []
    for d in days:
        cap, booked = by_day.get(d, (None, None))
        out.append(DayOutlook(
            day=d, capacity=cap, booked=booked,
            occupancy_pct=round(booked / cap * 100, 1) if cap else None,
            scheduled=sum(1 for s in scheduled_days if s == d),
        ))
    return out
