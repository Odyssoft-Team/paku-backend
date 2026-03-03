from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.push.domain.push import DeviceToken, DeviceTokenRepository, Platform, PushMessage


def _raise_device_error(code: str) -> None:
    if code == "device_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")


@dataclass
class RegisterDevice:
    repo: DeviceTokenRepository

    async def execute(self, *, user_id: UUID, platform: Platform, token: str) -> DeviceToken:
        return await self.repo.register_device(user_id=user_id, platform=platform, token=token)


@dataclass
class ListDevices:
    repo: DeviceTokenRepository

    async def execute(self, *, user_id: UUID) -> list[DeviceToken]:
        return await self.repo.list_devices(user_id=user_id)


@dataclass
class DeactivateDevice:
    repo: DeviceTokenRepository

    async def execute(self, *, user_id: UUID, device_id: UUID) -> DeviceToken:
        try:
            return await self.repo.deactivate_device(device_id=device_id, user_id=user_id)
        except ValueError as exc:
            _raise_device_error(str(exc))
            raise


@dataclass
class BroadcastPush:
    repo: DeviceTokenRepository

    async def execute(self, *, title: str, body: str, data: Optional[dict[str, Any]] = None) -> int:
        from app.core.settings import settings
        from app.modules.push.infra.provider import ExpoPushProvider, MockPushProvider

        tokens = await self.repo.get_all_active_tokens()
        if tokens:
            provider = ExpoPushProvider() if settings.ENV == "production" else MockPushProvider()
            provider.send(tokens=tokens, message=PushMessage(title=title, body=body, data=data))
        return len(tokens)
