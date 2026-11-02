"""Reporte de ventas (feature 0016): filas por orden de servicio, totales y resúmenes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException

from app.core.timezone import LIMA_TZ
from app.modules.geo.infra.districts_data import get_district_by_id
from app.modules.reports.domain.sales import (
    DATE_BASES,
    GroupTotal,
    SaleRow,
    SalesFilters,
    SalesTotals,
    group,
    in_range,
    matches,
    totals,
)


def _lima_day(when) -> Optional[date]:
    if when is None:
        return None
    if when.tzinfo is None:  # la BD guarda en UTC
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(LIMA_TZ).date()


def _lima_start(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=LIMA_TZ).astimezone(timezone.utc)


def _uuid(value) -> Optional[UUID]:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def _full_name(user) -> str:
    return f"{user.first_name} {user.last_name}".strip() if user else "Usuario eliminado"


def service_date(order) -> Optional[date]:
    """Cuando terminó; si no, la programada; si no, el día de la reserva."""
    return _lima_day(order.completed_at) or _lima_day(order.scheduled_at) or order.reserved_date


@dataclass(frozen=True)
class SalesReport:
    filters: SalesFilters
    rows: list[SaleRow]
    totals: SalesTotals
    by_service: list[GroupTotal]
    by_payment_method: list[GroupTotal]
    by_order_status: list[GroupTotal]
    options: dict[str, list[tuple[str, str]]]   # valores presentes en el rango de fechas, para los filtros


@dataclass
class BuildSalesReport:
    repo: Any   # PostgresSalesReadRepository

    async def execute(self, f: SalesFilters) -> SalesReport:
        if f.date_basis not in DATE_BASES:
            raise HTTPException(status_code=422, detail={
                "code": "DATE_BASIS_INVALID", "message": "Usa date_basis purchase o service.",
            })
        if f.date_from and f.date_to and f.date_from > f.date_to:
            raise HTTPException(status_code=422, detail={
                "code": "DATE_RANGE_INVALID", "message": "La fecha desde no puede ser posterior a la fecha hasta.",
            })
        # Con fecha de compra se acota en la consulta; con fecha del servicio se filtra después
        bounds = {}
        if f.date_basis == "purchase":
            bounds = dict(
                created_from=_lima_start(f.date_from) if f.date_from else None,
                created_to=_lima_start(f.date_to + timedelta(days=1)) if f.date_to else None,
            )
        orders = await self.repo.service_orders(**bounds)
        extras = await self.repo.paid_extras([o.id for o in orders])

        bases = {}
        for o in orders:
            base = next((l for l in o.items_snapshot or [] if isinstance(l, dict) and l.get("kind") == "service_base"), {})
            bases[o.id] = base
        pet_ids = {_uuid((b.get("meta") or {}).get("pet_id")) for b in bases.values() if isinstance(b.get("meta"), dict)}
        users = await self.repo.users(list({o.user_id for o in orders} | {o.groomer_id for o in orders if o.groomer_id}))
        pets = await self.repo.pet_names([p for p in pet_ids if p])
        campaigns = await self.repo.campaign_names(list({o.campaign_id for o in orders if o.campaign_id}))

        rows = []
        for o in orders:
            base = bases[o.id]
            meta = base.get("meta") if isinstance(base.get("meta"), dict) else {}
            items = [l for l in o.items_snapshot or [] if isinstance(l, dict)]
            subtotal = sum(float(l.get("unit_price") or 0) * float(l.get("qty") or 1) for l in items)
            total = float(o.total_snapshot)
            extra = round(extras.get(o.id, 0.0), 2)
            paid = o.payment_status.value == "paid"
            customer = users.get(o.user_id)
            groomer = users.get(o.groomer_id) if o.groomer_id else None
            district_id = (o.delivery_address_snapshot or {}).get("district_id")
            district = get_district_by_id(district_id) if district_id else None
            pet_id = _uuid(meta.get("pet_id"))
            rows.append(SaleRow(
                order_id=o.id, purchase_date=_lima_day(o.created_at), service_date=service_date(o),
                order_status=o.status.value, payment_status=o.payment_status.value,
                payment_method=o.payment_method.value if o.payment_method else None,
                customer_id=o.user_id, customer_name=_full_name(customer),
                customer_email=customer.email if customer else "", customer_phone=customer.phone if customer else None,
                pet_name=pets.get(pet_id) if pet_id else None,
                service_id=str(base.get("ref_id")) if base.get("ref_id") else None,
                service_name=base.get("name") or "Servicio",
                addon_names=[l.get("name") or "Adicional" for l in items if l.get("kind") == "service_addon"],
                subtotal=round(subtotal, 2), discount=round(float(o.discount_amount or 0), 2), total=round(total, 2),
                extra_paid=extra, collected=round((total if paid else 0.0) + extra, 2),
                groomer_id=o.groomer_id, groomer_name=_full_name(groomer) if groomer else None,
                district_id=district_id, district_name=district["name"] if district else None,
                campaign_id=o.campaign_id, campaign_name=campaigns.get(o.campaign_id) if o.campaign_id else None,
            ))

        dated = [r for r in rows if in_range(r, f)]
        result = [r for r in dated if matches(r, f)]
        result.sort(key=lambda r: (r.purchase_date, str(r.order_id)), reverse=True)

        def opts(key, label) -> list[tuple[str, str]]:
            seen = {key(r): label(r) for r in dated if key(r)}
            return sorted(((str(k), v) for k, v in seen.items()), key=lambda kv: kv[1])

        return SalesReport(
            filters=f, rows=result, totals=totals(result),
            by_service=group(result, lambda r: r.service_id, lambda r: r.service_name),
            by_payment_method=group(result, lambda r: r.payment_method, lambda r: r.payment_method or "sin medio"),
            by_order_status=group(result, lambda r: r.order_status, lambda r: r.order_status),
            options={
                "services": opts(lambda r: r.service_id, lambda r: r.service_name),
                "groomers": opts(lambda r: r.groomer_id, lambda r: r.groomer_name or ""),
                "districts": opts(lambda r: r.district_id, lambda r: r.district_name or r.district_id),
                "campaigns": opts(lambda r: r.campaign_id, lambda r: r.campaign_name or ""),
            },
        )
