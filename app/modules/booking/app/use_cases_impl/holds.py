from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.booking.app.use_cases_impl.availability import assert_hold_access
from app.modules.booking.domain.hold import Hold, HoldStatus
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository


@dataclass
class ConfirmHold:
    repo: PostgresHoldRepository

    async def execute(self, *, hold_id: UUID, requester_id: UUID, requester_role: str) -> Hold:
        hold = await self.repo.get_hold(hold_id)
        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hold not found")
        assert_hold_access(hold, requester_id=requester_id, requester_role=requester_role)
        if hold.status != HoldStatus.held:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hold cannot be confirmed")

        updated = await self.repo.update_status(hold_id, HoldStatus.confirmed)
        return updated or hold
