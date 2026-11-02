"""Capturas del inventario (feature 0015): foto fija del stock en una fecha de corte.

El stock de cada insumo en la captura es la suma de sus movimientos con fecha hasta el corte (incluido). La
captura guarda una copia de los datos del insumo para que no cambie si después se edita el insumo. Una captura
no se edita ni se borra.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

# Frecuencia de la captura automática (parámetro general `inventory_snapshot_frequency`)
FREQUENCIES: dict[str, str] = {
    "weekly": "Cada domingo",
    "semimonthly": "Día 15 y fin de mes",
    "monthly": "Fin de mes",
    "none": "Sin captura automática",
}
DEFAULT_FREQUENCY = "monthly"
# Si el servidor estuvo apagado, se recupera el último corte solo si no pasaron más de estos días
CATCH_UP_DAYS = 3

KINDS: dict[str, str] = {"scheduled": "Automática", "manual": "Manual"}


def _month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def is_cut_day(day: date, frequency: str) -> bool:
    if frequency == "weekly":
        return day.weekday() == 6  # domingo
    if frequency == "semimonthly":
        return day.day == 15 or day == _month_end(day)
    if frequency == "monthly":
        return day == _month_end(day)
    return False


def due_cut(today: date, frequency: str) -> Optional[date]:
    """Último corte ya terminado (antes de hoy) que todavía se puede tomar, o None."""
    for back in range(1, CATCH_UP_DAYS + 1):
        day = today - timedelta(days=back)
        if is_cut_day(day, frequency):
            return day
    return None


def next_cut(today: date, frequency: str) -> Optional[date]:
    """Próximo día de corte desde hoy (incluido: la captura se toma al terminar ese día)."""
    for ahead in range(0, 32):
        day = today + timedelta(days=ahead)
        if is_cut_day(day, frequency):
            return day
    return None


@dataclass(frozen=True)
class SnapshotLine:
    supply_id: UUID
    sku: str
    name: str
    category: str
    consumption_unit: str
    purchase_unit: str
    is_active: bool
    stock: float
    min_stock: float
    unit_cost: float
    value: float
    status: str               # ok | low | out


@dataclass(frozen=True)
class Snapshot:
    id: UUID
    cut_date: date
    kind: str                 # scheduled | manual
    frequency: Optional[str]  # la vigente al tomar una automática
    taken_at: datetime
    created_by: Optional[UUID]
    supplies_count: int
    total_value: float
    low_count: int
    out_count: int
    lines: list[SnapshotLine] = field(default_factory=list)
