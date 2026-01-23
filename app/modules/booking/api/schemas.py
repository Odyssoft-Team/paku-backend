from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.booking.domain.hold import HoldStatus


class HoldCreateIn(BaseModel):
    pet_id: UUID
    service_id: UUID


class HoldOut(BaseModel):
    id: UUID
    user_id: UUID
    pet_id: UUID
    service_id: UUID
    status: HoldStatus
    expires_at: datetime
    created_at: datetime


class AvailabilityOut(BaseModel):
    date: date
    capacity: int
    available: int
