from __future__ import annotations

import logging
from typing import Protocol

from app.modules.push.domain.push import PushMessage

logger = logging.getLogger(__name__)


class PushProvider(Protocol):
    def send(self, tokens: list[str], message: PushMessage) -> None:
        ...


class MockPushProvider(PushProvider):
    def send(self, tokens: list[str], message: PushMessage) -> None:
        logger.info("MockPushProvider.send tokens=%s title=%s", tokens, message.title)
        print({"provider": "mock", "tokens": tokens, "message": message.__dict__})


def get_push_provider() -> PushProvider:
    """Proveedor según PUSH_PROVIDER ("expo" | "mock"); ver app/core/settings.py."""
    from app.core.settings import settings

    return ExpoPushProvider() if settings.PUSH_PROVIDER == "expo" else MockPushProvider()


class ExpoPushProvider(PushProvider):
    def send(self, tokens: list[str], message: PushMessage) -> None:
        from exponent_server_sdk import (
            DeviceNotRegisteredError,
            PushClient,
            PushMessage as ExpoPushMessage,
            PushServerError,
            PushTicketError,
        )

        # sound/priority/channel_id: sin esto, en Android el aviso puede llegar sin sonido y sin
        # mostrarse arriba de la pantalla. La app crea el canal "default" con importancia alta.
        android_alert = {"sound": "default", "priority": "high", "channel_id": "default"}

        def _build(extra: dict) -> list:
            return [
                ExpoPushMessage(to=token, title=message.title, body=message.body, data=message.data or {}, **extra)
                for token in tokens
            ]

        try:
            push_messages = _build(android_alert)
        except TypeError:
            # Versión del SDK sin alguno de esos campos: enviar igual, sin ellos.
            logger.warning("Expo SDK no acepta sound/priority/channel_id; se envía sin ellos")
            push_messages = _build({})
        try:
            responses = PushClient().publish_multiple(push_messages)
            for response in responses:
                try:
                    response.validate_response()
                except DeviceNotRegisteredError:
                    logger.warning("Expo: token no registrado token=%s", response.push_message.to)
                except PushTicketError as exc:
                    logger.error("Expo: push ticket error %s", exc)
        except PushServerError as exc:
            logger.error("Expo: servidor error %s", exc)
        except Exception as exc:
            logger.error("Expo: error inesperado %s", exc)
