"""Reporte de ventas (feature 0016): servicios vendidos, una fila por orden de servicio.

- Una **venta** es una orden de servicio (sin orden padre). Los cargos extra (órdenes de ajuste) se suman a la
  orden que los originó, solo si están pagados.
- **Fecha de compra:** cuando se creó la orden (el checkout), en hora de Lima. **Fecha del servicio:** cuando
  terminó; si no, la programada; si no, la de la reserva.
- Montos: subtotal = suma de los ítems; descuento = el de la campaña; neto = `total_snapshot` (lo que se cobra);
  cobrado = neto si la orden está pagada + cargos extra pagados.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional
from uuid import UUID

DATE_BASES: dict[str, str] = {"purchase": "Fecha de compra", "service": "Fecha del servicio"}


@dataclass(frozen=True)
class SaleRow:
    order_id: UUID
    purchase_date: date
    service_date: Optional[date]
    order_status: str
    payment_status: str
    payment_method: Optional[str]
    customer_id: UUID
    customer_name: str
    customer_email: str
    customer_phone: Optional[str]
    pet_name: Optional[str]
    service_id: Optional[str]
    service_name: str
    addon_names: list[str]
    subtotal: float
    discount: float
    total: float              # neto (total_snapshot)
    extra_paid: float         # cargos extra pagados
    collected: float          # neto si está pagada + cargos extra pagados
    groomer_id: Optional[UUID]
    groomer_name: Optional[str]
    district_id: Optional[str]
    district_name: Optional[str]
    campaign_id: Optional[UUID]
    campaign_name: Optional[str]


@dataclass(frozen=True)
class SalesFilters:
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    date_basis: str = "purchase"
    order_status: Optional[str] = None
    payment_status: Optional[str] = None
    payment_method: Optional[str] = None
    service_id: Optional[str] = None
    groomer_id: Optional[UUID] = None
    district_id: Optional[str] = None
    campaign_id: Optional[UUID] = None
    q: Optional[str] = None


def _norm(text: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", text or "") if unicodedata.category(c) != "Mn").lower()


def row_day(row: SaleRow, basis: str) -> Optional[date]:
    return row.service_date if basis == "service" else row.purchase_date


def in_range(row: SaleRow, f: SalesFilters) -> bool:
    day = row_day(row, f.date_basis)
    if f.date_from is None and f.date_to is None:
        return True
    if day is None:
        return False
    return (f.date_from is None or day >= f.date_from) and (f.date_to is None or day <= f.date_to)


def matches(row: SaleRow, f: SalesFilters) -> bool:
    """Filtros distintos de la fecha."""
    if f.order_status and row.order_status != f.order_status:
        return False
    if f.payment_status and row.payment_status != f.payment_status:
        return False
    if f.payment_method and row.payment_method != f.payment_method:
        return False
    if f.service_id and row.service_id != f.service_id:
        return False
    if f.groomer_id and row.groomer_id != f.groomer_id:
        return False
    if f.district_id and row.district_id != f.district_id:
        return False
    if f.campaign_id and row.campaign_id != f.campaign_id:
        return False
    if f.q and f.q.strip():
        text = _norm(f.q.strip())
        haystack = _norm(" ".join(filter(None, [row.customer_name, row.customer_email, row.customer_phone,
                                                 row.pet_name, str(row.order_id)])))
        if text not in haystack:
            return False
    return True


@dataclass(frozen=True)
class SalesTotals:
    orders: int
    subtotal: float
    discount: float
    total: float
    extra_paid: float
    collected: float
    avg_ticket: Optional[float]   # cobrado ÷ órdenes pagadas
    cancelled: int


@dataclass(frozen=True)
class GroupTotal:
    key: Optional[str]
    label: str
    orders: int
    total: float
    collected: float


def totals(rows: list[SaleRow]) -> SalesTotals:
    paid = [r for r in rows if r.payment_status == "paid"]
    collected = round(sum(r.collected for r in rows), 2)
    return SalesTotals(
        orders=len(rows),
        subtotal=round(sum(r.subtotal for r in rows), 2),
        discount=round(sum(r.discount for r in rows), 2),
        total=round(sum(r.total for r in rows), 2),
        extra_paid=round(sum(r.extra_paid for r in rows), 2),
        collected=collected,
        avg_ticket=round(collected / len(paid), 2) if paid else None,
        cancelled=sum(1 for r in rows if r.order_status == "cancelled"),
    )


def group(rows: Iterable[SaleRow], key, label) -> list[GroupTotal]:
    """Totales por grupo, de mayor a menor monto cobrado."""
    out: dict[Optional[str], list] = {}
    for r in rows:
        k = key(r)
        entry = out.setdefault(k, [label(r), 0, 0.0, 0.0])
        entry[1] += 1
        entry[2] += r.total
        entry[3] += r.collected
    groups = [GroupTotal(k, v[0], v[1], round(v[2], 2), round(v[3], 2)) for k, v in out.items()]
    return sorted(groups, key=lambda g: (-g.collected, -g.orders, g.label))
