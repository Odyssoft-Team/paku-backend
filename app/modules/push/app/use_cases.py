import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.push.domain.push import DeviceToken, DeviceTokenRepository, Platform, PushMessage

logger = logging.getLogger(__name__)


async def send_push_to_user(user_id: UUID, *, title: str, body: str, data: Optional[dict[str, Any]] = None) -> int:
    """
    Envía un push a los dispositivos activos del usuario. Best-effort: nunca lanza, pero registra el
    error en el log (antes se tragaba sin rastro). Devuelve cuántos tokens se intentaron.

    Usa su propia sesión de BD (AsyncSessionLocal): `get_async_session` es una dependencia de FastAPI
    (generador) y no sirve con `async with`; usarla así fallaba siempre y el push nunca salía.
    """
    try:
        from app.core.db import AsyncSessionLocal, engine
        from app.modules.push.infra.postgres_device_repository import PostgresDeviceTokenRepository
        from app.modules.push.infra.provider import get_push_provider

        async with AsyncSessionLocal() as session:
            tokens = await PostgresDeviceTokenRepository(session=session, engine=engine).get_active_tokens(user_id)
        if not tokens:
            return 0
        # El SDK de Expo es síncrono (HTTP bloqueante): se ejecuta fuera del event loop.
        await asyncio.to_thread(
            get_push_provider().send, tokens=tokens, message=PushMessage(title=title, body=body, data=data),
        )
        return len(tokens)
    except Exception:
        logger.exception("No se pudo enviar el push al usuario %s", user_id)
        return 0


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
        from app.modules.push.infra.provider import get_push_provider

        tokens = await self.repo.get_all_active_tokens()
        if tokens:
            await asyncio.to_thread(
                get_push_provider().send, tokens=tokens, message=PushMessage(title=title, body=body, data=data),
            )
        return len(tokens)
