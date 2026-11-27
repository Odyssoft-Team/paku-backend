"""Gastos operativos y vehículos (feature 0026). Reglas puras, sin base de datos.

- Tipos de gasto según cómo se pagan: único (en su fecha, p. ej. combustible), mensual (cada mes desde su inicio hasta
  su fin, p. ej. internet) y anual (se paga una vez y se reparte en 12 meses, p. ej. el dominio).
- El monto que cuenta en el P&L es sin IGV: si lo pagado incluye IGV, se descuenta con el IGV de Parámetros generales.
- Un gasto se puede ligar a un vehículo. Se corrige editándolo o anulándolo con motivo; no se borra.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

ONE_TIME, MONTHLY, ANNUAL = "one_time", "monthly", "annual"
KINDS: dict[str, str] = {ONE_TIME: "Único", MONTHLY: "Mensual", ANNUAL: "Anual (se reparte en 12 meses)"}

# código → (etiqueta, grupo). Lista fija; «Otros» con descripción para lo demás.
CATEGORIES: dict[str, tuple[str, str]] = {
    "fuel": ("Combustible", "Vehículos"),
    "vehicle_maintenance": ("Mantenimiento y repuestos", "Vehículos"),
    "vehicle_insurance": ("Seguro y SOAT", "Vehículos"),
    "vehicle_parking": ("Cochera, peajes y estacionamiento", "Vehículos"),
    "vehicle_other": ("Otros del vehículo (revisión técnica, trámites)", "Vehículos"),
    "internet_phone": ("Internet y telefonía", "Servicios"),
    "utilities": ("Luz y agua del local", "Servicios"),
    "rent": ("Alquiler", "Servicios"),
    "domain_software": ("Dominio, hosting y software", "Tecnología"),
    "advertising": ("Publicidad y marketing", "Comercial"),
    "accounting_legal": ("Contador y legal", "Administración"),
    "bank_fees": ("Comisiones bancarias", "Administración"),
    "office": ("Útiles y oficina", "Administración"),
    "other": ("Otros", "Otros"),
}


class ExpenseInvalid(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class Vehicle:
    id: UUID
    name: str
    plate: Optional[str]
    brand: Optional[str]
    model: Optional[str]
    year: Optional[int]
    is_active: bool
    notes: Optional[str]
    created_at: datetime


@dataclass(frozen=True)
class Expense:
    id: UUID
    kind: str
    category: str
    description: str
    start_date: date              # fecha del gasto (único) o desde cuándo rige (mensual / anual)
    end_date: Optional[date]      # mensual: hasta cuándo (None = sigue vigente); anual: fin de los 12 meses
    total_paid: float             # lo pagado (con IGV si igv_included)
    igv_included: bool
    amount: float                 # sin IGV: lo que cuenta en el P&L (por mes en el mensual; total en único y anual)
    vehicle_id: Optional[UUID]
    supplier: Optional[str]
    document: Optional[str]
    notes: Optional[str]
    created_at: datetime
    created_by: Optional[UUID] = None
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None


def net_amount(total_paid: float, igv_included: bool, igv_percent: float) -> float:
    return round(total_paid / (1 + (igv_percent or 0) / 100), 2) if igv_included else round(total_paid, 2)


def annual_end(start: date) -> date:
    """Último día de los 12 meses que cubre un gasto anual (15/11/2026 → 14/11/2027)."""
    year = start.year + 1
    day = min(start.day, calendar.monthrange(year, start.month)[1])
    return date.fromordinal(date(year, start.month, day).toordinal() - 1)


def validate(*, kind: str, category: str, description: str, start_date: Optional[date], end_date: Optional[date],
             total_paid: Optional[float], today: date) -> None:
    if kind not in KINDS:
        raise ExpenseInvalid("kind", "El tipo es único, mensual o anual.")
    if category not in CATEGORIES:
        raise ExpenseInvalid("category", "Categoría no válida.")
    if not (description or "").strip():
        raise ExpenseInvalid("description", "Describe el gasto.")
    if start_date is None:
        raise ExpenseInvalid("start_date", "Indica la fecha.")
    if kind == ONE_TIME and start_date > today:
        raise ExpenseInvalid("start_date", "La fecha de un gasto único no puede ser futura.")
    if end_date is not None and (kind != MONTHLY or end_date < start_date):
        raise ExpenseInvalid("end_date", "Solo un gasto mensual tiene fecha de fin, y no puede ser anterior al inicio.")
    if total_paid is None or total_paid <= 0:
        raise ExpenseInvalid("total_paid", "El monto debe ser mayor que 0.")


def _monthly_allocation(per_month: float, active_from: date, active_to: Optional[date], start: date,
                        cut: date) -> float:
    """Monto mensual × días cubiertos ÷ días del mes, por cada mes entre `start` y `cut` en que está activo."""
    lo = max(start, active_from)
    hi = cut if active_to is None else min(cut, active_to)
    total, day = 0.0, lo
    while day <= hi:
        days_in_month = calendar.monthrange(day.year, day.month)[1]
        until = min(date(day.year, day.month, days_in_month), hi)
        total += per_month * ((until - day).days + 1) / days_in_month
        day = date.fromordinal(until.toordinal() + 1)
    return total


def allocation(expense: Expense, start: date, cut: date) -> float:
    """Lo que el gasto aporta al período [start, cut] (sin IGV). Anulado = 0."""
    if expense.is_voided or cut < start:
        return 0.0
    if expense.kind == ONE_TIME:
        return expense.amount if start <= expense.start_date <= cut else 0.0
    if expense.kind == MONTHLY:
        return round(_monthly_allocation(expense.amount, expense.start_date, expense.end_date, start, cut), 2)
    return round(_monthly_allocation(expense.amount / 12, expense.start_date, annual_end(expense.start_date),
                                     start, cut), 2)


def coverage_end(expense: Expense) -> Optional[date]:
    """Hasta cuándo afecta el gasto (None = mensual sin fin)."""
    if expense.kind == ONE_TIME:
        return expense.start_date
    if expense.kind == ANNUAL:
        return annual_end(expense.start_date)
    return expense.end_date
