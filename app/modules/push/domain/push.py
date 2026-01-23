from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol
from uuid import UUID, uuid4


class Platform(str, Enum):
    android = "android"
    ios = "ios"
    web = "web"


@dataclass(frozen=True)
class DeviceToken:
    id: UUID
    user_id: UUID
    platform: Platform
    token: str
    is_active: bool
    created_at: datetime

    @staticmethod
    def new(*, user_id: UUID, platform: Platform, token: str) -> "DeviceToken":
        return DeviceToken(
            id=uuid4(),
            user_id=user_id,
            platform=platform,
            token=token,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    data: Optional[dict[str, Any]] = None


class DeviceTokenRepository(Protocol):
    def register_device(self, user_id: UUID, platform: Platform, token: str) -> DeviceToken:
        ...

    def list_devices(self, user_id: UUID) -> list[DeviceToken]:
        ...

    def deactivate_device(self, device_id: UUID, user_id: UUID) -> DeviceToken:
        ...

    def get_active_tokens(self, user_id: UUID) -> list[str]:
        ...
