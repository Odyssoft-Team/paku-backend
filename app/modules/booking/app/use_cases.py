from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.booking.domain.hold import Hold, HoldStatus
from app.modules.booking.infra.hold_repository import create_hold, get_hold, update_status


@dataclass
class CreateHold:
    def execute(self, *, user_id: UUID, pet_id: UUID, service_id: UUID) -> Hold:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        return create_hold(user_id=user_id, pet_id=pet_id, service_id=service_id, expires_at=expires_at)


@dataclass
class ConfirmHold:
    def execute(self, *, hold_id: UUID) -> Hold:
        hold = get_hold(hold_id)
        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hold not found")
        if hold.status != HoldStatus.held:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hold cannot be confirmed")
        updated = update_status(hold_id, HoldStatus.confirmed)
        return updated or hold


@dataclass
class CancelHold:
    def execute(self, *, hold_id: UUID) -> Hold:
        hold = get_hold(hold_id)
        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hold not found")
        if hold.status == HoldStatus.cancelled:
            return hold
        if hold.status != HoldStatus.held:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hold cannot be cancelled")
        updated = update_status(hold_id, HoldStatus.cancelled)
        return updated or hold
