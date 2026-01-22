from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.commerce.domain.service import ServiceType, Species


class ServiceOut(BaseModel):
    id: UUID
    name: str
    type: ServiceType
    species: Species
    allowed_breeds: Optional[List[str]]
    requires: Optional[List[UUID]]
    is_active: bool


class ServiceAvailableOut(ServiceOut):
    available_addons: List[ServiceOut]


class QuoteIn(BaseModel):
    pet_id: UUID
    base_service_id: UUID
    addon_ids: Optional[List[UUID]] = None


class QuoteLineOut(BaseModel):
    service_id: UUID
    name: str
    price: int


class QuoteOut(BaseModel):
    pet_id: UUID
    base: QuoteLineOut
    addons: List[QuoteLineOut]
    total: int
    currency: str = "PEN"
