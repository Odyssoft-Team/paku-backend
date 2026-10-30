from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CustomerPetBriefOut(BaseModel):
    id: UUID
    name: str
    species: str


class CustomerSummaryOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    district_id: Optional[str] = None
    district_name: Optional[str] = None
    registered_at: datetime
    pets: list[CustomerPetBriefOut]
    services: int = Field(description="Órdenes de servicio terminadas")
    spend: float = Field(description="Pagado: órdenes + cargos extra pagados")
    avg_ticket: float
    first_visit: Optional[date] = None
    last_visit: Optional[date] = None
    days_since_last_visit: Optional[int] = None
    avg_interval_days: Optional[int] = Field(default=None, description="Días promedio entre visitas")
    segment: Optional[str] = Field(default=None, description="vip | recurrente | nuevo | sin_recompra | en_riesgo | inactivo")


class SegmentOut(BaseModel):
    code: str
    label: str
    rule: str
    count: int


class CustomerStatsOut(BaseModel):
    customers: int
    pets: int
    active: int = Field(description="Vinieron en los últimos 45 días")
    active_pct: Optional[float] = None
    with_repurchase: int = Field(description="2 o más servicios")
    repurchase_pct: Optional[float] = None
    total_spend: float
    avg_spend: Optional[float] = None
    segments: list[SegmentOut]


class CustomerPetOut(BaseModel):
    id: UUID
    name: str
    species: str
    breed_id: Optional[str] = None
    breed_name: Optional[str] = None
    weight_kg: Optional[float] = None
    weight_code: Optional[str] = Field(default=None, description="Tramo de peso W01…W06")
    birth_date: Optional[date] = None
    grooming_frequency: Optional[str] = None
    receive_reminders: Optional[bool] = None
    antiparasitic: Optional[bool] = None
    antiparasitic_interval: Optional[str] = None
    services: int


class CustomerVisitOut(BaseModel):
    order_id: UUID
    date: date
    pet_id: Optional[UUID] = None
    pet_name: Optional[str] = None
    service_name: str
    addon_names: list[str]
    amount: float = Field(description="Pagado: orden + cargos extra pagados")
    paid: bool


class CustomerDetailOut(CustomerSummaryOut):
    pets_detail: list[CustomerPetOut]
    visits: list[CustomerVisitOut] = Field(description="De la más reciente a la más antigua")
