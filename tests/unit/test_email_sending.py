"""Feature 0018 fase 2: envío con registro (idempotencia, estados, reintentos) y consulta del registro.
SQLite en memoria; proveedor falso (sin red); reloj controlado."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.settings import settings
from app.modules.messaging.app.sender import EmailSender
from app.modules.messaging.app.use_cases import (
    ListNotificationLogs,
    RetryNotificationLog,
    SendTestEmail,
    UpdateEmailIntegration,
)
from app.modules.messaging.domain.email import BaseEmailProvider, EmailMessage, EmailProviderError, SendResult
from app.modules.messaging.domain.logs import MAX_ATTEMPTS, next_attempt_at
from app.modules.messaging.infra.models import ChannelProviderModel, NotificationLogModel
from app.modules.messaging.infra.postgres_channel_repository import PostgresChannelRepository
from app.modules.messaging.infra.postgres_log_repository import PostgresLogRepository

KEY = "re_12345678_abcdefgh9aXz"
T0 = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)  # 10:00 en Lima


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())


class Clock:
    def __init__(self):
        self.at = T0

    def __call__(self):
        return self.at

    def advance(self, **kw):
        self.at += timedelta(**kw)


class ScriptedProvider(BaseEmailProvider):
    """Responde según una lista: None = aceptado; EmailProviderError = rechazado."""
    code = "resend"

    def __init__(self, *script):
        self.script, self.calls = list(script), []

    async def send(self, message, *, sender, idempotency_key=None):
        self.calls.append((message, idempotency_key))
        outcome = self.script.pop(0) if self.script else None
        if outcome is not None:
            raise outcome
        return SendResult(provider_message_id=f"msg_{len(self.calls)}")


def _run(coro):
    return asyncio.run(coro)


async def _env(fn, *, enabled=True, configure=True):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all,
                            tables=[ChannelProviderModel.__table__, NotificationLogModel.__table__])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        channels, logs = PostgresChannelRepository(session=session), PostgresLogRepository(session=session)
        if configure:
            await UpdateEmailIntegration(repo=channels).execute(
                provider="resend", enabled=enabled, api_key=KEY, from_email="hola@paku.com.pe", from_name="Paku",
                reply_to=None, actor_id=uuid4())
        return await fn(channels, logs)
    finally:
        await session.close()
        await engine.dispose()


def _sender(channels, logs, provider, clock):
    return EmailSender(channels=channels, logs=logs, provider_factory=lambda code, key: provider, now=clock)


MSG = EmailMessage(to=["ana@correo.pe"], subject="Tu próximo baño", html="<p>Hola</p>", text="Hola")


def test_next_attempt_backoff():
    assert [next_attempt_at(n, now=T0) - T0 for n in (1, 2, 3, 4)] == [
        timedelta(minutes=m) for m in (1, 5, 15, 60)]
    assert next_attempt_at(MAX_ATTEMPTS, now=T0) is None


def test_sent_once_per_idempotency_key():
    async def scenario(channels, logs):
        provider, clock = ScriptedProvider(), Clock()
        sender = _sender(channels, logs, provider, clock)
        user = uuid4()
        log = await sender.send(MSG, idempotency_key="reminder:bath:1", template="reminder_bath", user_id=user)
        assert (log.status, log.attempts, log.provider_message_id, log.sent_at) == ("SENT", 1, "msg_1", T0)
        assert (log.recipient, log.subject, log.user_id, log.provider) == (
            "ana@correo.pe", "Tu próximo baño", user, "resend")
        assert provider.calls[0][1] == "reminder:bath:1"  # la clave también va al proveedor

        again = await sender.send(MSG, idempotency_key="reminder:bath:1")
        assert again.id == log.id and len(provider.calls) == 1
    _run(_env(scenario))


def test_disabled_or_unconfigured_fails_without_calling_provider():
    async def disabled(channels, logs):
        provider = ScriptedProvider()
        log = await _sender(channels, logs, provider, Clock()).send(MSG, idempotency_key="k1")
        assert (log.status, log.retryable, log.attempts, log.error) == (
            "FAILED", False, 0, "El envío de correos está desactivado.")
        assert provider.calls == []
    _run(_env(disabled, enabled=False))

    async def missing(channels, logs):
        log = await _sender(channels, logs, ScriptedProvider(), Clock()).send(MSG, idempotency_key="k1")
        assert log.status == "FAILED" and log.error.startswith("El correo no está configurado")
    _run(_env(missing, configure=False))


def test_temporary_failure_is_retried_until_sent():
    async def scenario(channels, logs):
        busy = EmailProviderError("Resend respondió 429: Too many requests", retryable=True, status_code=429)
        provider, clock = ScriptedProvider(busy, busy), Clock()
        sender = _sender(channels, logs, provider, clock)
        log = await sender.send(MSG, idempotency_key="k1")
        assert (log.status, log.retryable, log.attempts, log.next_attempt_at) == (
            "FAILED", True, 1, T0 + timedelta(minutes=1))

        assert await sender.retry_due() == 0          # todavía no toca
        clock.advance(minutes=1)
        assert await sender.retry_due() == 1          # 2.º intento: falla otra vez, espera 5 min
        log = await logs.get(log.id)
        assert (log.status, log.attempts, log.next_attempt_at) == ("FAILED", 2, clock.at + timedelta(minutes=5))
        clock.advance(minutes=5)
        assert await sender.retry_due() == 1          # 3.º: sale
        log = await logs.get(log.id)
        assert (log.status, log.attempts, log.retryable, log.error, log.next_attempt_at) == (
            "SENT", 3, False, None, None)
        assert {key for _, key in provider.calls} == {"k1"}  # siempre la misma clave
    _run(_env(scenario))


def test_permanent_failure_and_max_attempts_are_not_retried():
    async def scenario(channels, logs):
        clock = Clock()
        bad = EmailProviderError("Resend respondió 422: Invalid `to` field", retryable=False, status_code=422)
        log = await _sender(channels, logs, ScriptedProvider(bad), clock).send(MSG, idempotency_key="k1")
        assert (log.status, log.retryable, log.next_attempt_at) == ("FAILED", False, None)

        down = EmailProviderError("caído", retryable=True, status_code=500)
        sender = _sender(channels, logs, ScriptedProvider(*[down] * MAX_ATTEMPTS), clock)
        log = await sender.send(MSG, idempotency_key="k2")
        for _ in range(MAX_ATTEMPTS - 1):
            clock.advance(hours=2)
            await sender.retry_due()
        log = await logs.get(log.id)
        assert (log.attempts, log.status, log.retryable, log.next_attempt_at) == (MAX_ATTEMPTS, "FAILED", False, None)
        clock.advance(hours=2)
        assert await sender.retry_due() == 0
    _run(_env(scenario))


def test_stuck_pending_is_retried_with_same_key():
    async def scenario(channels, logs):
        clock = Clock()
        log = NotificationLogModel(id=uuid4(), channel="email", idempotency_key="k1", recipient="ana@correo.pe",
                                   subject="Hola", payload={"to": ["ana@correo.pe"], "html": "<p>Hola</p>"},
                                   status="PENDING", retryable=False, attempts=1, created_at=T0, updated_at=T0)
        await logs.add(log)
        provider = ScriptedProvider()
        sender = _sender(channels, logs, provider, clock)
        clock.advance(minutes=9)
        assert await sender.retry_due() == 0
        clock.advance(minutes=1)
        assert await sender.retry_due() == 1
        log = await logs.get(log.id)
        assert (log.status, log.attempts) == ("SENT", 2)
        message, key = provider.calls[0]
        assert (message.to, message.html, key) == (["ana@correo.pe"], "<p>Hola</p>", "k1")
    _run(_env(scenario))


def test_manual_retry():
    async def scenario(channels, logs):
        bad = EmailProviderError("Resend respondió 403: domain not verified", status_code=403)
        provider, clock = ScriptedProvider(bad), Clock()
        failed = await _sender(channels, logs, provider, clock).send(MSG, idempotency_key="k1")
        retry = RetryNotificationLog(repo=channels, logs=logs, provider_factory=lambda c, k: provider)
        sent = await retry.execute(failed.id)
        assert (sent.status, sent.attempts) == ("SENT", 2)
        with pytest.raises(HTTPException) as exc:
            await retry.execute(failed.id)
        assert (exc.value.status_code, exc.value.detail["code"]) == (409, "LOG_NOT_RETRYABLE")
        with pytest.raises(HTTPException) as exc:
            await retry.execute(uuid4())
        assert exc.value.detail["code"] == "LOG_NOT_FOUND"
    _run(_env(scenario))


def test_test_email_is_logged_without_auto_retry():
    async def scenario(channels, logs):
        down = EmailProviderError("caído", retryable=True, status_code=503)
        result = await SendTestEmail(repo=channels, logs=logs, provider_factory=lambda c, k: ScriptedProvider(down)
                                     ).execute(to="admin@paku.com.pe")
        assert (result.ok, result.error) == (False, "caído")
        page = await ListNotificationLogs(logs=logs).execute(channel="email", status=None, q=None, date_from=None,
                                                             date_to=None, limit=50, offset=0)
        (log,) = page.items
        assert (log.template, log.status, log.retryable) == ("test", "FAILED", False)
    _run(_env(scenario, enabled=False))  # la prueba sale aunque esté desactivado


def test_list_filters_and_counts():
    async def scenario(channels, logs):
        clock = Clock()
        bad = EmailProviderError("rechazado", status_code=422)
        sender = _sender(channels, logs, ScriptedProvider(None, bad, None), clock)
        await sender.send(MSG, idempotency_key="a")
        clock.advance(minutes=1)
        await sender.send(EmailMessage(to=["beto@correo.pe"], subject="Cupón"), idempotency_key="b")
        clock.advance(days=1)
        await sender.send(MSG, idempotency_key="c")

        lst = ListNotificationLogs(logs=logs)

        async def page(**kw):
            args = dict(channel="email", status=None, q=None, date_from=None, date_to=None, limit=50, offset=0)
            args.update(kw)
            return await lst.execute(**args)

        p = await page()
        assert (p.total, p.counts) == (3, {"PENDING": 0, "SENT": 2, "FAILED": 1})
        assert [i.idempotency_key for i in p.items] == ["c", "b", "a"]  # más recientes primero
        p = await page(status="FAILED")
        assert (p.total, [i.recipient for i in p.items], p.counts["SENT"]) == (1, ["beto@correo.pe"], 2)
        assert (await page(q="CUPÓN".lower())).total == 1
        assert (await page(q="ana@")).total == 2
        p = await page(date_from=date(2026, 11, 2), date_to=date(2026, 11, 2))  # día de Lima
        assert p.total == 2
        assert [i.idempotency_key for i in (await page(limit=1, offset=1)).items] == ["b"]
        for kw, code in [(dict(status="DONE"), "LOG_STATUS_INVALID"),
                         (dict(date_from=date(2026, 11, 3), date_to=date(2026, 11, 2)), "DATE_RANGE_INVALID")]:
            with pytest.raises(HTTPException) as exc:
                await page(**kw)
            assert exc.value.detail["code"] == code
    _run(_env(scenario))
