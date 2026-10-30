"""Clientes (feature 0011): servicios, gasto, frecuencia, última visita y segmento de cada dueño.

Un **servicio** (visita) es una orden de servicio terminada (`done`, sin `parent_order_id`). Su monto es lo
pagado: la orden (si está pagada) más sus cargos extra pagados (órdenes de ajuste). Las reglas de segmento
son las de la maqueta del admin (CRM · Clientes) y se evalúan en este orden.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from uuid import UUID

ACTIVE_DAYS = 45            # "activo": vino en los últimos 45 días
NEW_DAYS = 30
INACTIVE_DAYS = 75
RISK_MIN_DAYS = 45
RISK_FACTOR = 1.5
VIP_WINDOW_DAYS = 180
VIP_MIN_SERVICES = 5

SEGMENTS: dict[str, tuple[str, str]] = {
    "vip": ("VIP", "5 o más servicios en los últimos 6 meses y vino hace poco"),
    "recurrente": ("Recurrente", "2 o más servicios y viene dentro de su frecuencia habitual"),
    "nuevo": ("Nuevo", "Primer servicio en los últimos 30 días"),
    "sin_recompra": ("Sin recompra", "Un solo servicio hace más de 30 días y no volvió"),
    "en_riesgo": ("En riesgo", "Pasó 1,5 veces su frecuencia habitual (mín. 45 días) sin volver"),
    "inactivo": ("Inactivo", "Más de 75 días sin un servicio"),
}


@dataclass(frozen=True)
class Visit:
    order_id: UUID
    day: date
    pet_id: Optional[UUID]
    service_name: str
    addon_names: list[str]
    amount: float               # pagado: orden + cargos extra pagados
    paid: bool


@dataclass(frozen=True)
class CustomerMetrics:
    services: int
    spend: float
    avg_ticket: float
    first_visit: Optional[date]
    last_visit: Optional[date]
    days_since_last_visit: Optional[int]
    avg_interval_days: Optional[int]     # días promedio entre visitas; None con una sola fecha
    segment: Optional[str]               # None si no tiene servicios
    visits: list[Visit] = field(default_factory=list)   # de la más antigua a la más reciente


def segment_for(*, services: int, days_since: int, days_since_first: int, interval: Optional[int],
                services_last_6m: int) -> str:
    if days_since > INACTIVE_DAYS:
        return "inactivo"
    if interval and days_since > max(RISK_MIN_DAYS, interval * RISK_FACTOR):
        return "en_riesgo"
    if services == 1:
        return "nuevo" if days_since_first <= NEW_DAYS else "sin_recompra"
    if services_last_6m >= VIP_MIN_SERVICES:
        return "vip"
    return "recurrente"


def compute_metrics(visits: list[Visit], *, today: date) -> CustomerMetrics:
    visits = sorted(visits, key=lambda v: (v.day, str(v.order_id)))
    if not visits:
        return CustomerMetrics(0, 0.0, 0.0, None, None, None, None, None, [])
    spend = round(sum(v.amount for v in visits), 2)
    days = sorted({v.day for v in visits})
    first, last = days[0], days[-1]
    days_since = (today - last).days
    interval = round((last - first).days / (len(days) - 1)) if len(days) > 1 else None
    last_6m = sum(1 for v in visits if (today - v.day).days <= VIP_WINDOW_DAYS)
    segment = segment_for(services=len(visits), days_since=days_since, days_since_first=(today - first).days,
                          interval=interval, services_last_6m=last_6m)
    return CustomerMetrics(
        services=len(visits), spend=spend, avg_ticket=round(spend / len(visits), 2), first_visit=first,
        last_visit=last, days_since_last_visit=days_since, avg_interval_days=interval, segment=segment,
        visits=visits,
    )


def visit_from_order(order, adjustments: list, day: date) -> Visit:
    """Visita desde una orden terminada y sus órdenes de ajuste (`adjustments`)."""
    base = next((l for l in order.items_snapshot or [] if isinstance(l, dict) and l.get("kind") == "service_base"), {})
    addons = [l.get("name") or "Adicional" for l in order.items_snapshot or []
              if isinstance(l, dict) and l.get("kind") == "service_addon"]
    meta = base.get("meta") if isinstance(base.get("meta"), dict) else {}
    try:
        pet_id = UUID(str(meta.get("pet_id"))) if meta.get("pet_id") else None
    except ValueError:
        pet_id = None
    paid = order.payment_status.value == "paid"
    amount = (float(order.total_snapshot) if paid else 0.0) + sum(
        float(a.total_snapshot) for a in adjustments if a.payment_status.value == "paid"
    )
    return Visit(order_id=order.id, day=day, pet_id=pet_id, service_name=base.get("name") or "Servicio",
                 addon_names=addons, amount=round(amount, 2), paid=paid)
