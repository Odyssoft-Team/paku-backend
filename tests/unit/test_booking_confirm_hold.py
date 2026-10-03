import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.modules.booking.app.use_cases_impl.holds import ConfirmHold
from app.modules.booking.domain.hold import Hold, HoldStatus


class _FakeHoldRepo:
    def __init__(self, hold: Hold | None):
        self._hold = hold
        self.update_calls: list[tuple[UUID, HoldStatus]] = []

    async def get_hold(self, hold_id: UUID) -> Hold | None:
        if self._hold is None:
            return None
        if self._hold.id != hold_id:
            return None
        return self._hold

    async def update_status(self, hold_id: UUID, status: HoldStatus):
        self.update_calls.append((hold_id, status))
        if self._hold is None or self._hold.id != hold_id:
            return None
        self._hold = replace(self._hold, status=status)
        return self._hold


def _hold(status: HoldStatus = HoldStatus.held) -> Hold:
    now = datetime.now(timezone.utc)
    return Hold(
        id=uuid4(),
        user_id=uuid4(),
        pet_id=uuid4(),
        service_id=uuid4(),
        status=status,
        expires_at=now,
        created_at=now,
        quote_snapshot=None,
    )


def test_confirm_hold_updates_status_to_confirmed():
    hold = _hold()
    repo = _FakeHoldRepo(hold)

    out = asyncio.run(ConfirmHold(repo=repo).execute(
        hold_id=hold.id, requester_id=hold.user_id, requester_role="user",
    ))

    assert out.status == HoldStatus.confirmed
    assert repo.update_calls == [(hold.id, HoldStatus.confirmed)]


def test_confirm_hold_nonexistent_returns_404():
    repo = _FakeHoldRepo(None)

    with pytest.raises(HTTPException) as err:
        asyncio.run(ConfirmHold(repo=repo).execute(hold_id=uuid4(), requester_id=uuid4(), requester_role="user"))

    assert err.value.status_code == 404


def test_confirm_hold_expired_returns_409():
    hold = _hold(HoldStatus.expired)
    repo = _FakeHoldRepo(hold)

    with pytest.raises(HTTPException) as err:
        asyncio.run(ConfirmHold(repo=repo).execute(
            hold_id=hold.id, requester_id=hold.user_id, requester_role="user",
        ))

    assert err.value.status_code == 409
    assert repo.update_calls == []


def test_confirm_hold_of_another_user_returns_403():
    hold = _hold()
    repo = _FakeHoldRepo(hold)

    with pytest.raises(HTTPException) as err:
        asyncio.run(ConfirmHold(repo=repo).execute(hold_id=hold.id, requester_id=uuid4(), requester_role="user"))

    assert err.value.status_code == 403
    assert repo.update_calls == []


def test_admin_can_confirm_any_hold():
    hold = _hold()
    repo = _FakeHoldRepo(hold)

    out = asyncio.run(ConfirmHold(repo=repo).execute(hold_id=hold.id, requester_id=uuid4(), requester_role="admin"))

    assert out.status == HoldStatus.confirmed
