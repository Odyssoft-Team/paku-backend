from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol
from uuid import UUID, uuid4


# [TECH]
# Enum defining supported push notification platforms.
#
# [NATURAL/BUSINESS]
# Tipos de dispositivos que pueden recibir notificaciones.
class Platform(str, Enum):
    android = "android"
    ios = "ios"
    web = "web"


# [TECH]
# Immutable entity storing device push token per user/platform.
#
# [NATURAL/BUSINESS]
# Token de dispositivo para enviar notificaciones push.
@dataclass(frozen=True)
class DeviceToken:
    id: UUID
    user_id: UUID
    platform: Platform
    token: str
    is_active: bool
    created_at: datetime

    # [TECH]
    # Factory creating active DeviceToken with UUID and timestamp.
    #
    # [NATURAL/BUSINESS]
    # Crea un nuevo token de dispositivo activo.
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


# [TECH]
# Value object for push notification payload.
#
# [NATURAL/BUSINESS]
# Mensaje de notificación con título y contenido.
@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    data: Optional[dict[str, Any]] = None


# [TECH]
# Repository interface for device token persistence.
#
# [NATURAL/BUSINESS]
# Guarda y gestiona tokens de dispositivos push.
class DeviceTokenRepository(Protocol):
    async def register_device(self, user_id: UUID, platform: Platform, token: str) -> DeviceToken:
        ...

    async def list_devices(self, user_id: UUID) -> list[DeviceToken]:
        ...

    async def deactivate_device(self, device_id: UUID, user_id: UUID) -> DeviceToken:
        ...

    async def get_active_tokens(self, user_id: UUID) -> list[str]:
        ...
