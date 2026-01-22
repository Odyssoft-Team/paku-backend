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
