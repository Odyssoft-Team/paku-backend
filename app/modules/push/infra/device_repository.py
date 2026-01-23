from __future__ import annotations

from typing import Dict, List
from uuid import UUID

from app.modules.push.domain.push import DeviceToken, DeviceTokenRepository, Platform


class InMemoryDeviceTokenRepository(DeviceTokenRepository):
    def __init__(self) -> None:
        self._by_id: Dict[UUID, DeviceToken] = {}
        self._by_user: Dict[UUID, List[UUID]] = {}

    def register_device(self, user_id: UUID, platform: Platform, token: str) -> DeviceToken:
        ids = self._by_user.get(user_id, [])

        existing_id: UUID | None = None
        for device_id in ids:
            device = self._by_id.get(device_id)
            if device is None:
                continue
            if device.platform == platform:
                existing_id = device.id
                break

        if existing_id is not None:
            prev = self._by_id[existing_id]
            updated = DeviceToken(
                id=prev.id,
                user_id=prev.user_id,
                platform=prev.platform,
                token=token,
                is_active=True,
                created_at=prev.created_at,
            )
            self._by_id[existing_id] = updated
            return updated

        device = DeviceToken.new(user_id=user_id, platform=platform, token=token)
        self._by_id[device.id] = device
        if user_id not in self._by_user:
            self._by_user[user_id] = []
        self._by_user[user_id].append(device.id)
        return device

    def list_devices(self, user_id: UUID) -> list[DeviceToken]:
        ids = self._by_user.get(user_id, [])
        out: List[DeviceToken] = []
        for device_id in ids:
            device = self._by_id.get(device_id)
            if device is None:
                continue
            out.append(device)
        return out

    def deactivate_device(self, device_id: UUID, user_id: UUID) -> DeviceToken:
        device = self._by_id.get(device_id)
        if not device or device.user_id != user_id:
            raise ValueError("device_not_found")

        if not device.is_active:
            return device

        updated = DeviceToken(
            id=device.id,
            user_id=device.user_id,
            platform=device.platform,
            token=device.token,
            is_active=False,
            created_at=device.created_at,
        )
        self._by_id[device_id] = updated
        return updated

    def get_active_tokens(self, user_id: UUID) -> list[str]:
        devices = self.list_devices(user_id)
        return [d.token for d in devices if d.is_active]
