"""Costo del groomer (feature 0012): sueldo, cargos y horas → costo por hora de servicio. Solo admin."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.core.timezone import today_lima
from app.modules.groomer_costs.api.schemas import (
    CostItemOut,
    CostProfileIn,
    CostProfileOut,
    GroomerCostOut,
    GroomerCostsOut,
    SuggestedItemOut,
)
from app.modules.groomer_costs.app.use_cases import GetLaborRates, SaveCostProfile
from app.modules.groomer_costs.domain.costs import SUGGESTED_ITEMS, CostProfile, profile_on
from app.modules.groomer_costs.infra.postgres_cost_repository import PostgresCostRepository

admin_router = APIRouter(prefix="/groomer-costs", tags=["groomer-costs-admin"])


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresCostRepository:
    return PostgresCostRepository(session=session)


def _profile_out(p: CostProfile, current_id) -> CostProfileOut:
    return CostProfileOut(
        id=p.id, groomer_id=p.groomer_id, effective_from=p.effective_from, base_salary=p.base_salary,
        items=[CostItemOut(label=i.label, kind=i.kind, value=i.value, monthly_amount=round(i.monthly_amount(p.base_salary), 2))
               for i in p.items],
        monthly_cost=round(p.monthly_cost, 2), monthly_hours=p.monthly_hours, driving_rest_hours=p.driving_rest_hours,
        service_hours=p.service_hours, cost_per_hour=round(p.cost_per_hour, 2),
        cost_per_service_hour=round(p.cost_per_service_hour, 2), is_current=p.id == current_id, notes=p.notes,
        created_at=p.created_at,
    )


@admin_router.get("", response_model=GroomerCostsOut)
async def list_groomer_costs(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCostRepository = Depends(get_repo),
) -> GroomerCostsOut:
    """Cada groomer con su registro de costo vigente hoy y la tarifa de referencia de las recetas."""
    rates = await GetLaborRates(repo=repo).execute()
    groomers = []
    for g in await repo.groomers():
        current = rates.by_groomer.get(g.id)
        groomers.append(GroomerCostOut(
            groomer_id=g.id, first_name=g.first_name, last_name=g.last_name, is_active=bool(g.is_active),
            current=_profile_out(current, current.id) if current else None,
        ))
    return GroomerCostsOut(
        groomers=groomers,
        reference_rate=round(rates.reference, 2) if rates.reference is not None else None,
        suggested_items=[SuggestedItemOut(label=l, kind=k, value=v) for l, k, v in SUGGESTED_ITEMS],
    )


@admin_router.get("/{groomer_id}", response_model=list[CostProfileOut])
async def groomer_cost_history(
    groomer_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCostRepository = Depends(get_repo),
) -> list[CostProfileOut]:
    """Historial de registros de costo del groomer (el más reciente primero)."""
    profiles = await repo.list_profiles(groomer_id=groomer_id)
    current = profile_on(profiles, today_lima())
    return [_profile_out(p, current.id if current else None) for p in profiles]


@admin_router.post("/{groomer_id}", response_model=CostProfileOut, status_code=status.HTTP_201_CREATED)
async def save_groomer_cost(
    groomer_id: UUID,
    payload: CostProfileIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCostRepository = Depends(get_repo),
) -> CostProfileOut:
    """
    Registra el costo del groomer desde `effective_from`. Un registro en la misma fecha se reemplaza (para
    corregir). Los servicios anteriores siguen con el registro de su fecha.
    """
    profile = await SaveCostProfile(repo=repo).execute(
        groomer_id=groomer_id, effective_from=payload.effective_from, base_salary=payload.base_salary,
        items=[i.model_dump() for i in payload.items], monthly_hours=payload.monthly_hours,
        driving_rest_hours=payload.driving_rest_hours, notes=payload.notes, actor_id=current.id,
    )
    profiles = await repo.list_profiles(groomer_id=groomer_id)
    now = profile_on(profiles, today_lima())
    return _profile_out(profile, now.id if now else None)
