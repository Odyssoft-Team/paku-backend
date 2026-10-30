"""Clientes (feature 0011): resumen por dueño desde sus órdenes. Solo admin."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.modules.crm.api.schemas import (
    CustomerDetailOut,
    CustomerPetBriefOut,
    CustomerPetOut,
    CustomerStatsOut,
    CustomerSummaryOut,
    CustomerVisitOut,
    SegmentOut,
)
from app.modules.crm.app.use_cases import Customer, GetCustomer, GetCustomerStats, ListCustomers
from app.modules.crm.domain.customers import SEGMENTS
from app.modules.crm.infra.postgres_customer_read_repository import PostgresCustomerReadRepository
from app.modules.inventory.domain.inventory import weight_code_for

admin_router = APIRouter(prefix="/customers", tags=["crm-admin"])


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresCustomerReadRepository:
    return PostgresCustomerReadRepository(session=session)


def _summary(c: Customer) -> dict:
    m, u = c.metrics, c.user
    return dict(
        id=u.id, first_name=u.first_name, last_name=u.last_name, email=u.email, phone=u.phone,
        district_id=c.district_id, district_name=c.district_name, registered_at=u.created_at,
        pets=[CustomerPetBriefOut(id=p.id, name=p.name, species=p.species) for p in c.pets],
        services=m.services, spend=m.spend, avg_ticket=m.avg_ticket, first_visit=m.first_visit,
        last_visit=m.last_visit, days_since_last_visit=m.days_since_last_visit,
        avg_interval_days=m.avg_interval_days, segment=m.segment,
    )


def _pct(part: int, total: int) -> Optional[float]:
    return round(part / total * 100, 1) if total else None


@admin_router.get("", response_model=list[CustomerSummaryOut])
async def list_customers(
    segment: Optional[str] = Query(None, description="vip|recurrente|nuevo|sin_recompra|en_riesgo|inactivo"),
    district_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Nombre, correo, teléfono o nombre de mascota"),
    last_visit_from: Optional[date] = Query(None),
    last_visit_to: Optional[date] = Query(None),
    sort: str = Query("spend", description="spend | last_visit | services (de mayor a menor)"),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCustomerReadRepository = Depends(get_repo),
) -> list[CustomerSummaryOut]:
    """Dueños con al menos un servicio terminado: gasto, frecuencia, última visita y segmento."""
    customers = await ListCustomers(repo=repo).execute(
        segment=segment, district_id=district_id, q=q, last_visit_from=last_visit_from,
        last_visit_to=last_visit_to, sort=sort,
    )
    return [CustomerSummaryOut(**_summary(c)) for c in customers]


@admin_router.get("/stats", response_model=CustomerStatsOut)
async def customer_stats(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCustomerReadRepository = Depends(get_repo),
) -> CustomerStatsOut:
    """Totales de clientes (sin filtros) y cuántos hay en cada segmento, con su regla."""
    s = await GetCustomerStats(repo=repo).execute()
    return CustomerStatsOut(
        customers=s.customers, pets=s.pets, active=s.active, active_pct=_pct(s.active, s.customers),
        with_repurchase=s.with_repurchase, repurchase_pct=_pct(s.with_repurchase, s.customers),
        total_spend=s.total_spend, avg_spend=s.avg_spend,
        segments=[SegmentOut(code=code, label=label, rule=rule, count=s.by_segment[code])
                  for code, (label, rule) in SEGMENTS.items()],
    )


@admin_router.get("/{user_id}", response_model=CustomerDetailOut)
async def get_customer(
    user_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCustomerReadRepository = Depends(get_repo),
) -> CustomerDetailOut:
    """Ficha del cliente: contacto, mascotas, historial de servicios y métricas (también sin servicios)."""
    c = await GetCustomer(repo=repo).execute(user_id)
    pet_names = {p.id: p.name for p in c.pets}
    services_by_pet: dict[UUID, int] = {}
    for v in c.metrics.visits:
        if v.pet_id:
            services_by_pet[v.pet_id] = services_by_pet.get(v.pet_id, 0) + 1
    return CustomerDetailOut(
        **_summary(c),
        pets_detail=[
            CustomerPetOut(
                id=p.id, name=p.name, species=p.species, breed_id=p.breed_id, breed_name=p.breed_name,
                weight_kg=p.weight_kg, weight_code=weight_code_for(p.weight_kg), birth_date=p.birth_date,
                grooming_frequency=p.grooming_frequency, receive_reminders=p.receive_reminders,
                antiparasitic=p.antiparasitic, antiparasitic_interval=p.antiparasitic_interval,
                services=services_by_pet.get(p.id, 0),
            )
            for p in c.pets
        ],
        visits=[
            CustomerVisitOut(
                order_id=v.order_id, date=v.day, pet_id=v.pet_id, pet_name=pet_names.get(v.pet_id),
                service_name=v.service_name, addon_names=v.addon_names, amount=v.amount, paid=v.paid,
            )
            for v in reversed(c.metrics.visits)
        ],
    )
