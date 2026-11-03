"""Feature 0018: configuración del correo (cifrado, máscara, guardado, prueba) y proveedor Resend.
SQLite en memoria para el repositorio; Resend con un transporte httpx simulado (sin red)."""
import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import crypto
from app.core.base import Base
from app.core.settings import settings
from app.modules.messaging.app.use_cases import GetEmailIntegration, SendTestEmail, UpdateEmailIntegration
from app.modules.messaging.domain.email import (
    BaseEmailProvider,
    EmailMessage,
    EmailProviderError,
    Sender,
    SendResult,
    mask_secret,
)
from app.modules.messaging.infra.models import ChannelProviderModel, NotificationLogModel
from app.modules.messaging.infra.postgres_channel_repository import PostgresChannelRepository
from app.modules.messaging.infra.postgres_log_repository import PostgresLogRepository
from app.modules.messaging.infra.resend_provider import RESEND_URL, ResendEmailProvider

ADMIN = uuid4()
KEY = "re_12345678_abcdefgh9aXz"


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())


def _run(coro):
    return asyncio.run(coro)


async def _with_repo(fn):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[ChannelProviderModel.__table__,
                                                                    NotificationLogModel.__table__])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        repo = PostgresChannelRepository(session=session)
        repo.logs = PostgresLogRepository(session=session)
        return await fn(repo)
    finally:
        await session.close()
        await engine.dispose()


def _update(repo, **kw):
    data = dict(provider="resend", enabled=False, api_key=None, from_email=None, from_name=None, reply_to=None)
    data.update(kw)
    return UpdateEmailIntegration(repo=repo).execute(**data, actor_id=ADMIN)


def test_crypto_roundtrip_and_rotation(monkeypatch):
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    token = crypto.encrypt_secret(KEY, key=old)
    assert token != KEY and crypto.decrypt_secret(token, key=old) == KEY
    assert crypto.decrypt_secret(token, key=f"{new},{old}") == KEY      # rotación: la vieja aún descifra
    with pytest.raises(crypto.CryptoUnavailable):
        crypto.decrypt_secret(token, key=new)
    monkeypatch.setattr(settings, "CREDENTIALS_ENCRYPTION_KEY", None)
    assert crypto.encryption_ready() is False
    with pytest.raises(crypto.CryptoUnavailable):
        crypto.encrypt_secret(KEY)
    monkeypatch.setattr(settings, "CREDENTIALS_ENCRYPTION_KEY", "no-es-una-llave")
    assert crypto.encryption_ready() is False


def test_mask_secret():
    assert mask_secret(KEY) == "re_12…9aXz"
    assert mask_secret("re_short") == "…rt"


def test_save_masks_and_encrypts_and_keeps_key():
    async def scenario(repo):
        empty = await GetEmailIntegration(repo=repo).execute()
        assert (empty.status, empty.configured, empty.api_key_mask, empty.encryption_ready) == (
            "not_configured", False, None, True)

        view = await _update(repo, api_key=f"  {KEY} ", from_email="Hola@Paku.com.pe", from_name="Paku",
                             reply_to="soporte@paku.com.pe", enabled=True)
        assert (view.status, view.api_key_mask, view.from_email, view.reply_to) == (
            "active", "re_12…9aXz", "Hola@paku.com.pe", "soporte@paku.com.pe")
        stored = await repo.get("email")
        assert KEY not in stored.secret_encrypted and crypto.decrypt_secret(stored.secret_encrypted) == KEY

        # Sin api_key: se conserva la guardada
        view = await _update(repo, api_key="", from_email="hola@paku.com.pe", enabled=False)
        assert (view.status, view.api_key_mask, view.from_name) == ("disabled", "re_12…9aXz", None)
        assert crypto.decrypt_secret((await repo.get("email")).secret_encrypted) == KEY
    _run(_with_repo(scenario))


@pytest.mark.parametrize("kw,field", [
    (dict(enabled=True, from_email="hola@paku.com.pe"), "api_key"),            # activar sin key
    (dict(enabled=True, api_key=KEY), "from_email"),                           # activar sin remitente
    (dict(api_key="sk_otra_cosa_123456"), "api_key"),                          # no es de Resend
    (dict(api_key=KEY, from_email="hola@"), "from_email"),
    (dict(api_key=KEY, reply_to="soporte"), "reply_to"),
    (dict(api_key=KEY, from_name="Paku <x>"), "from_name"),
    (dict(provider="sendgrid", api_key=KEY), "provider"),
])
def test_invalid_config_saves_nothing(kw, field):
    async def scenario(repo):
        with pytest.raises(HTTPException) as exc:
            await _update(repo, **kw)
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "EMAIL_CONFIG_INVALID" and exc.value.detail["field"] == field
        assert await repo.get("email") is None
    _run(_with_repo(scenario))


def test_saving_key_without_encryption_key_is_503(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIALS_ENCRYPTION_KEY", "")

    async def scenario(repo):
        with pytest.raises(HTTPException) as exc:
            await _update(repo, api_key=KEY)
        assert (exc.value.status_code, exc.value.detail["code"]) == (503, "ENCRYPTION_UNAVAILABLE")
    _run(_with_repo(scenario))


class FakeProvider(BaseEmailProvider):
    code = "resend"

    def __init__(self, fail=None):
        self.fail, self.sent = fail, []

    async def send(self, message, *, sender, idempotency_key=None):
        if self.fail:
            raise EmailProviderError(self.fail, status_code=403)
        self.sent.append((message, sender))
        return SendResult(provider_message_id="msg_1")


def test_send_test_email_records_last_result():
    async def scenario(repo):
        with pytest.raises(HTTPException) as exc:
            await SendTestEmail(repo=repo, logs=repo.logs).execute(to="admin@paku.com.pe")
        assert (exc.value.status_code, exc.value.detail["code"]) == (409, "EMAIL_NOT_CONFIGURED")

        await _update(repo, api_key=KEY, from_email="hola@paku.com.pe", from_name="Paku", enabled=True)
        ok = FakeProvider()
        seen_keys = []

        def factory(code, api_key):
            seen_keys.append((code, api_key))
            return ok
        result = await SendTestEmail(repo=repo, logs=repo.logs, provider_factory=factory).execute(to="admin@paku.com.pe")
        assert (result.ok, result.provider_message_id, seen_keys) == (True, "msg_1", [("resend", KEY)])
        message, sender = ok.sent[0]
        assert (message.to, sender.formatted) == (["admin@paku.com.pe"], "Paku <hola@paku.com.pe>")

        bad = FakeProvider(fail="Resend respondió 403: The paku.com.pe domain is not verified.")
        result = await SendTestEmail(repo=repo, logs=repo.logs, provider_factory=lambda c, k: bad).execute(to="admin@paku.com.pe")
        assert (result.ok, result.error) == (False, "Resend respondió 403: The paku.com.pe domain is not verified.")
        view = await GetEmailIntegration(repo=repo).execute()
        assert (view.status, view.last_test_ok) == ("error", False)

        # Cambiar la key borra la última prueba: la configuración nueva no está probada
        view = await _update(repo, api_key="re_otra_key_1234567890", from_email="hola@paku.com.pe", enabled=True)
        assert (view.status, view.last_test_at, view.last_test_ok) == ("active", None, None)
    _run(_with_repo(scenario))


def _resend(handler):
    return ResendEmailProvider(KEY, transport=httpx.MockTransport(handler))


def test_resend_request_and_errors():
    captured = {}

    def ok(request):
        captured.update(url=str(request.url), headers=request.headers, body=json.loads(request.content))
        return httpx.Response(200, json={"id": "4ef9a417"})

    msg = EmailMessage(to=["ana@correo.pe"], subject="Hola", html="<p>Hola</p>", text="Hola", tags={"category": "test"})
    sender = Sender(from_email="hola@paku.com.pe", from_name="Paku", reply_to="soporte@paku.com.pe")
    result = _run(_resend(ok).send(msg, sender=sender, idempotency_key="order-1:reminder"))
    assert result.provider_message_id == "4ef9a417"
    assert captured["url"] == RESEND_URL
    assert captured["headers"]["authorization"] == f"Bearer {KEY}"
    assert captured["headers"]["idempotency-key"] == "order-1:reminder"
    assert captured["body"] == {"from": "Paku <hola@paku.com.pe>", "to": ["ana@correo.pe"], "subject": "Hola",
                                "html": "<p>Hola</p>", "text": "Hola", "reply_to": "soporte@paku.com.pe",
                                "tags": [{"name": "category", "value": "test"}]}

    for status, retryable in [(422, False), (403, False), (429, True), (500, True)]:
        provider = _resend(lambda r, s=status: httpx.Response(s, json={"name": "x", "message": "detalle"}))
        with pytest.raises(EmailProviderError) as exc:
            _run(provider.send(msg, sender=sender))
        assert (exc.value.status_code, exc.value.retryable) == (status, retryable)
        assert exc.value.message == f"Resend respondió {status}: detalle"

    def down(request):
        raise httpx.ConnectError("sin red")
    with pytest.raises(EmailProviderError) as exc:
        _run(_resend(down).send(msg, sender=sender))
    assert exc.value.retryable is True
