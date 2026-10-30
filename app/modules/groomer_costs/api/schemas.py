from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CostItemIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    kind: Literal["percent", "amount"] = Field(description="percent = % del sueldo; amount = S/ al mes")
    value: float = Field(ge=0)


class CostItemOut(CostItemIn):
    monthly_amount: float = Field(description="S/ al mes")


class CostProfileIn(BaseModel):
    effective_from: date = Field(description="Desde qué día rige; otro registro en la misma fecha lo reemplaza")
    base_salary: float = Field(gt=0, description="Sueldo mensual (S/)")
    items: list[CostItemIn] = Field(default_factory=list, description="Cargos de la empresa sobre el sueldo")
    monthly_hours: float = Field(gt=0, description="Horas de trabajo al mes")
    driving_rest_hours: float = Field(ge=0, description="Bolsón de manejo y reposo dentro de esas horas")
    notes: Optional[str] = Field(default=None, max_length=500)


class CostProfileOut(BaseModel):
    id: UUID
    groomer_id: UUID
    effective_from: date
    base_salary: float
    items: list[CostItemOut]
    monthly_cost: float = Field(description="Sueldo + cargos: lo que la empresa paga al mes")
    monthly_hours: float
    driving_rest_hours: float
    service_hours: float = Field(description="Horas al mes − manejo y reposo")
    cost_per_hour: float = Field(description="Costo mensual ÷ horas al mes (referencial)")
    cost_per_service_hour: float = Field(description="Costo mensual ÷ horas de servicio: costea las recetas")
    is_current: bool = Field(description="Es el registro que rige hoy")
    notes: Optional[str] = None
    created_at: datetime


class GroomerCostOut(BaseModel):
    groomer_id: UUID
    first_name: str
    last_name: str
    is_active: bool
    current: Optional[CostProfileOut] = None


class SuggestedItemOut(BaseModel):
    label: str
    kind: str
    value: float


class GroomerCostsOut(BaseModel):
    groomers: list[GroomerCostOut]
    reference_rate: Optional[float] = Field(
        default=None, description="Costo por hora de servicio con que se estiman las recetas (promedio de los vigentes)",
    )
    suggested_items: list[SuggestedItemOut]
