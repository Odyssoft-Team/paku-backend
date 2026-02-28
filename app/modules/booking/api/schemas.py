from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.booking.domain.hold import HoldStatus


class HoldCreateIn(BaseModel):
    pet_id: UUID
    service_id: UUID
    date: date


class HoldOut(BaseModel):
    id: UUID
    user_id: UUID
    pet_id: UUID
    service_id: UUID
    status: HoldStatus
    expires_at: datetime
    created_at: datetime
    date: Optional[date] = None


class AvailabilityOut(BaseModel):
    id: UUID
    service_id: UUID
    date: date
    capacity: int
    booked: int
    available: int
    is_active: bool


# ------------------------------------------------------------------
# Admin schemas
# ------------------------------------------------------------------

class AvailabilitySlotCreateIn(BaseModel):
    service_id: UUID
    date: date
    capacity: int = Field(gt=0)
    is_active: bool = True


class AvailabilitySlotUpdateIn(BaseModel):
    capacity: int = Field(gt=0)


class AvailabilitySlotToggleIn(BaseModel):
    is_active: bool
