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
