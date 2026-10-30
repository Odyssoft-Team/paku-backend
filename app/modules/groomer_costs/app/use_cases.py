"""Costo del groomer (feature 0012)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.timezone import today_lima
from app.modules.groomer_costs.domain.costs import (
    CostItem,
    CostProfile,
    CostProfileInvalid,
    profile_on,
    reference_rate,
    validate_profile,
)


@dataclass(frozen=True)
class LaborRates:
    """Tarifas por hora de servicio en una fecha: la de cada groomer y la de referencia (promedio)."""
    day: date
    by_groomer: dict[UUID, CostProfile]
    reference: Optional[float]

    def rate_for(self, groomer_id: Optional[UUID]) -> tuple[Optional[float], str]:
        """Tarifa para una orden: la de su groomer o, si no tiene registro, la de referencia."""
        profile = self.by_groomer.get(groomer_id) if groomer_id else None
        if profile is not None:
            return profile.cost_per_service_hour, "groomer"
        return self.reference, "reference"


@dataclass
class GetLaborRates:
    repo: Any

    async def execute(self, *, day: Optional[date] = None) -> LaborRates:
        day = day or today_lima()
        by_groomer: dict[UUID, list[CostProfile]] = {}
        for p in await self.repo.list_profiles():
            by_groomer.setdefault(p.groomer_id, []).append(p)
        current = {gid: p for gid, ps in by_groomer.items() if (p := profile_on(ps, day)) is not None}
        return LaborRates(day=day, by_groomer=current, reference=reference_rate(list(current.values())))


@dataclass
class SaveCostProfile:
    repo: Any

    async def execute(
        self,
        *,
        groomer_id: UUID,
        effective_from: date,
        base_salary: float,
        items: list[dict],
        monthly_hours: float,
        driving_rest_hours: float,
        notes: Optional[str],
        actor_id: UUID,
    ) -> CostProfile:
        """Registra el costo del groomer desde `effective_from` (si ya hay uno en esa fecha, lo corrige)."""
        if groomer_id not in {g.id for g in await self.repo.groomers()}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "code": "GROOMER_NOT_FOUND", "message": "No existe un groomer con ese id.",
            })
        cost_items = [CostItem(label=(i["label"] or "").strip(), kind=i["kind"], value=float(i["value"])) for i in items]
        try:
            validate_profile(base_salary=base_salary, items=cost_items, monthly_hours=monthly_hours,
                             driving_rest_hours=driving_rest_hours)
        except CostProfileInvalid as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from exc
        return await self.repo.save_profile(
            groomer_id=groomer_id, effective_from=effective_from, base_salary=base_salary, items=cost_items,
            monthly_hours=monthly_hours, driving_rest_hours=driving_rest_hours, notes=notes, created_by=actor_id,
        )


async def labor_rates(session, *, day: Optional[date] = None) -> LaborRates:
    """Tarifas de mano de obra para otros módulos (inventario)."""
    from app.modules.groomer_costs.infra.postgres_cost_repository import PostgresCostRepository

    return await GetLaborRates(repo=PostgresCostRepository(session=session)).execute(day=day)
