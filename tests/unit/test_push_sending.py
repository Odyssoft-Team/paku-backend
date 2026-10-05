"""Envío de push: proveedor según PUSH_PROVIDER y sesión de BD correcta (antes el push nunca salía)."""
import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from app.core.settings import settings
from app.modules.push.app import use_cases as push_uc
from app.modules.push.infra import provider as push_provider


@pytest.mark.parametrize("value,expected", [("expo", push_provider.ExpoPushProvider),
                                            ("mock", push_provider.MockPushProvider)])
def test_provider_follows_push_provider_setting(monkeypatch, value, expected):
    monkeypatch.setattr(settings, "PUSH_PROVIDER", value)
    assert isinstance(push_provider.get_push_provider(), expected)


def test_send_push_to_user_uses_a_real_session_and_sends(monkeypatch):
    sent = []
    user_id = uuid4()

    class _Repo:
        def __init__(self, *, session, engine):
            pass

        async def get_active_tokens(self, uid):
            return ["ExponentPushToken[abc]"] if uid == user_id else []

    class _Provider:
        def send(self, tokens, message):
            sent.append((tokens, message.title, message.data))

    @asynccontextmanager
    async def _session():
        yield object()

    import app.core.db as db
    import app.modules.push.infra.postgres_device_repository as devices

    monkeypatch.setattr(db, "AsyncSessionLocal", _session)
    monkeypatch.setattr(devices, "PostgresDeviceTokenRepository", _Repo)
    monkeypatch.setattr(push_provider, "get_push_provider", lambda: _Provider())

    count = asyncio.run(push_uc.send_push_to_user(user_id, title="Nueva parada asignada", body="x",
                                                  data={"order_id": "1", "type": "order_assigned"}))

    assert count == 1
    assert sent == [(["ExponentPushToken[abc]"], "Nueva parada asignada", {"order_id": "1", "type": "order_assigned"})]


def test_send_push_never_raises(monkeypatch):
    import app.core.db as db

    @asynccontextmanager
    async def _broken():
        raise RuntimeError("BD caída")
        yield  # pragma: no cover

    monkeypatch.setattr(db, "AsyncSessionLocal", _broken)
    assert asyncio.run(push_uc.send_push_to_user(uuid4(), title="t", body="b")) == 0
