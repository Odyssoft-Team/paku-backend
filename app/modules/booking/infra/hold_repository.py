from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from app.modules.booking.domain.hold import Hold, HoldStatus


class InMemoryHoldRepository:
    def __init__(self) -> None:
        self._by_id: Dict[UUID, Hold] = {}

    def _maybe_expire(self, hold: Hold) -> Hold:
        if hold.status in (HoldStatus.cancelled, HoldStatus.confirmed, HoldStatus.expired):
            return hold
        now = datetime.now(timezone.utc)
        if hold.expires_at <= now:
            expired = Hold(
                id=hold.id,
                user_id=hold.user_id,
                pet_id=hold.pet_id,
                service_id=hold.service_id,
                status=HoldStatus.expired,
                expires_at=hold.expires_at,
                created_at=hold.created_at,
            )
            self._by_id[hold.id] = expired
            return expired
        return hold

    def create_hold(self, *, user_id: UUID, pet_id: UUID, service_id: UUID, expires_at: datetime) -> Hold:
        created_at = datetime.now(timezone.utc)
        hold = Hold.new(
            user_id=user_id,
            pet_id=pet_id,
            service_id=service_id,
            expires_at=expires_at,
            created_at=created_at,
        )
        self._by_id[hold.id] = hold
        return hold

    def get_hold(self, hold_id: UUID) -> Optional[Hold]:
        hold = self._by_id.get(hold_id)
        if not hold:
            return None
        return self._maybe_expire(hold)

    def update_status(self, hold_id: UUID, status: HoldStatus) -> Optional[Hold]:
        hold = self.get_hold(hold_id)
        if not hold:
            return None
        if hold.status == HoldStatus.expired:
            return hold
        if hold.status == HoldStatus.held and status not in (HoldStatus.confirmed, HoldStatus.cancelled):
            return hold
        if hold.status in (HoldStatus.confirmed, HoldStatus.cancelled):
            return hold

        updated = Hold(
            id=hold.id,
            user_id=hold.user_id,
            pet_id=hold.pet_id,
            service_id=hold.service_id,
            status=status,
            expires_at=hold.expires_at,
            created_at=hold.created_at,
        )
        self._by_id[hold.id] = updated
        return updated

    def list_by_user(self, user_id: UUID) -> List[Hold]:
        out: List[Hold] = []
        for hold in self._by_id.values():
            if hold.user_id == user_id:
                out.append(self._maybe_expire(hold))
        return out


_repo = InMemoryHoldRepository()


def create_hold(*, user_id: UUID, pet_id: UUID, service_id: UUID, expires_at: datetime) -> Hold:
    return _repo.create_hold(user_id=user_id, pet_id=pet_id, service_id=service_id, expires_at=expires_at)


def get_hold(hold_id: UUID) -> Optional[Hold]:
    return _repo.get_hold(hold_id)


def update_status(hold_id: UUID, status: HoldStatus) -> Optional[Hold]:
    return _repo.update_status(hold_id, status)


def list_by_user(user_id: UUID) -> List[Hold]:
    return _repo.list_by_user(user_id)
