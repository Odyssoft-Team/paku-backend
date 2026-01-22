from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class HoldStatus(str, Enum):
    held = "held"
    confirmed = "confirmed"
    cancelled = "cancelled"
    expired = "expired"


@dataclass(frozen=True)
class Hold:
    id: UUID
    user_id: UUID
    pet_id: UUID
    service_id: UUID
    status: HoldStatus
    expires_at: datetime
    created_at: datetime

    @staticmethod
    def new(*, user_id: UUID, pet_id: UUID, service_id: UUID, expires_at: datetime, created_at: datetime) -> "Hold":
        return Hold(
            id=uuid4(),
            user_id=user_id,
            pet_id=pet_id,
            service_id=service_id,
            status=HoldStatus.held,
            expires_at=expires_at,
            created_at=created_at,
        )
