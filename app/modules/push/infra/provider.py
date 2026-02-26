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


class ExpoPushProvider(PushProvider):
    def send(self, tokens: list[str], message: PushMessage) -> None:
        from exponent_server_sdk import (
            DeviceNotRegisteredError,
            PushClient,
            PushMessage as ExpoPushMessage,
            PushServerError,
            PushTicketError,
        )

        push_messages = [
            ExpoPushMessage(
                to=token,
                title=message.title,
                body=message.body,
                data=message.data or {},
            )
            for token in tokens
        ]
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
