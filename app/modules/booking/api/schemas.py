# `date` se importa con alias: HoldOut tiene un campo llamado `date` con valor por defecto, y en
# `date: Optional[date] = None` el nombre del campo tapaba al tipo (Pydantic lo tomaba como None → 500).
from datetime import date as date_type, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.booking.domain.hold import HoldStatus


class HoldCreateIn(BaseModel):
    pet_id: UUID
    service_id: UUID
    date: date_type


class HoldOut(BaseModel):
    id: UUID
    user_id: UUID
    pet_id: UUID
    service_id: UUID
    status: HoldStatus
    expires_at: datetime
    created_at: datetime
    date: Optional[date_type] = None


class AvailabilityOut(BaseModel):
    id: UUID
    service_id: UUID
    service_name: Optional[str] = None
    date: date_type
    capacity: int
    booked: int
    available: int
    is_active: bool


# ------------------------------------------------------------------
# Admin schemas
# ------------------------------------------------------------------

class AvailabilitySlotCreateIn(BaseModel):
    service_id: UUID
    date: date_type
    capacity: int = Field(gt=0)
    is_active: bool = True


class AvailabilitySlotUpdateIn(BaseModel):
    capacity: int = Field(gt=0)


class AvailabilitySlotToggleIn(BaseModel):
    is_active: bool


class AvailabilitySlotBulkCreateIn(BaseModel):
    service_id: UUID
    date_from: date_type
    date_to: Optional[date_type] = None
    capacity: int = Field(gt=0)
    is_active: bool = True


class AvailabilitySlotBulkOut(BaseModel):
    created: list[AvailabilityOut]
    skipped: list[date_type]
