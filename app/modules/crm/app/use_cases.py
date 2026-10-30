"""Clientes (feature 0011): resumen por dueño calculado desde sus órdenes."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.timezone import LIMA_TZ, today_lima
from app.modules.crm.domain.customers import ACTIVE_DAYS, SEGMENTS, CustomerMetrics, compute_metrics, visit_from_order
from app.modules.geo.infra.districts_data import get_district_by_id

SORTS = ("spend", "last_visit", "services")


@dataclass(frozen=True)
class Customer:
    user: Any                     # UserModel
    district_id: Optional[str]
    district_name: Optional[str]
    pets: list                    # PetModel
    metrics: CustomerMetrics

    @property
    def full_name(self) -> str:
        return f"{self.user.first_name} {self.user.last_name}".strip()


def _visit_day(order) -> date:
    """Día (en Lima) del servicio: cuando terminó; si no hay, el programado o la creación."""
    when = order.completed_at or order.scheduled_at or order.created_at
    if when.tzinfo is None:  # la BD guarda en UTC
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(LIMA_TZ).date()


def _norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text or "") if unicodedata.category(c) != "Mn").lower()


def _matches(c: Customer, q: str) -> bool:
    text = _norm(q.strip())
    digits = "".join(ch for ch in q if ch.isdigit())
    if text in _norm(c.full_name) or text in _norm(c.user.email):
        return True
    if digits and digits in "".join(ch for ch in (c.user.phone or "") if ch.isdigit()):
        return True
    return any(text in _norm(p.name) for p in c.pets)


@dataclass
class BuildCustomers:
    repo: Any

    async def execute(self, *, user_id: Optional[UUID] = None, today: Optional[date] = None) -> list[Customer]:
        """Clientes con al menos un servicio (o el cliente `user_id`, aunque no tenga)."""
        today = today or today_lima()
        orders = await self.repo.service_orders(user_id=user_id)
        adjustments: dict[UUID, list] = {}
        for o in orders:
            if o.parent_order_id is not None:
                adjustments.setdefault(o.parent_order_id, []).append(o)
        by_user: dict[UUID, list] = {}
        last_district: dict[UUID, tuple] = {}
        for o in orders:
            if o.parent_order_id is not None:
                continue
            day = _visit_day(o)
            by_user.setdefault(o.user_id, []).append(visit_from_order(o, adjustments.get(o.id, []), day))
            snapshot = o.delivery_address_snapshot or {}
            if snapshot.get("district_id") and (o.user_id not in last_district or day > last_district[o.user_id][0]):
                last_district[o.user_id] = (day, snapshot["district_id"])

        ids = list(by_user) if user_id is None else [user_id]
        users = await self.repo.users(ids)
        defaults = await self.repo.default_district_ids(ids)
        pets = await self.repo.pets_by_owner(ids)
        out = []
        for uid in ids:
            user = users.get(uid)
            if user is None:
                continue
            # Distrito: dirección principal, luego el del perfil y si no, el de su último servicio
            district_id = defaults.get(uid) or user.address_district_id or last_district.get(uid, (None, None))[1]
            district = get_district_by_id(district_id) if district_id else None
            out.append(Customer(
                user=user, district_id=district_id, district_name=district["name"] if district else None,
                pets=pets.get(uid, []), metrics=compute_metrics(by_user.get(uid, []), today=today),
            ))
        return out


@dataclass
class ListCustomers:
    repo: Any

    async def execute(
        self,
        *,
        segment: Optional[str] = None,
        district_id: Optional[str] = None,
        q: Optional[str] = None,
        last_visit_from: Optional[date] = None,
        last_visit_to: Optional[date] = None,
        sort: str = "spend",
    ) -> list[Customer]:
        if segment is not None and segment not in SEGMENTS:
            raise HTTPException(status_code=422, detail={
                "code": "SEGMENT_INVALID", "message": "Segmento inválido. Usa uno de: " + ", ".join(SEGMENTS) + ".",
            })
        if sort not in SORTS:
            raise HTTPException(status_code=422, detail={
                "code": "SORT_INVALID", "message": "Orden inválido. Usa uno de: " + ", ".join(SORTS) + ".",
            })
        rows = [
            c for c in await BuildCustomers(repo=self.repo).execute()
            if (not segment or c.metrics.segment == segment)
            and (not district_id or c.district_id == district_id)
            and (not last_visit_from or c.metrics.last_visit >= last_visit_from)
            and (not last_visit_to or c.metrics.last_visit <= last_visit_to)
            and (not q or not q.strip() or _matches(c, q))
        ]
        key = {
            "spend": lambda c: c.metrics.spend,
            "services": lambda c: c.metrics.services,
            "last_visit": lambda c: c.metrics.last_visit,
        }[sort]
        return sorted(rows, key=lambda c: (key(c), c.full_name), reverse=True)


@dataclass(frozen=True)
class CustomerStats:
    customers: int
    pets: int
    active: int                   # vinieron en los últimos ACTIVE_DAYS días
    with_repurchase: int          # 2 o más servicios
    total_spend: float
    avg_spend: Optional[float]
    by_segment: dict[str, int]


@dataclass
class GetCustomerStats:
    repo: Any

    async def execute(self) -> CustomerStats:
        rows = await BuildCustomers(repo=self.repo).execute()
        total = round(sum(c.metrics.spend for c in rows), 2)
        return CustomerStats(
            customers=len(rows),
            pets=sum(len(c.pets) for c in rows),
            active=sum(1 for c in rows if c.metrics.days_since_last_visit <= ACTIVE_DAYS),
            with_repurchase=sum(1 for c in rows if c.metrics.services > 1),
            total_spend=total,
            avg_spend=round(total / len(rows), 2) if rows else None,
            by_segment={code: sum(1 for c in rows if c.metrics.segment == code) for code in SEGMENTS},
        )


@dataclass
class GetCustomer:
    repo: Any

    async def execute(self, user_id: UUID) -> Customer:
        found = await BuildCustomers(repo=self.repo).execute(user_id=user_id)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "code": "CUSTOMER_NOT_FOUND", "message": "Cliente no encontrado.",
            })
        return found[0]
