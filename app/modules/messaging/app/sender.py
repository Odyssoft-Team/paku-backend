"""Envío de correos con registro (feature 0018 fase 2). Punto de entrada para el resto del backend:

    log = await send_email(session, to="ana@correo.pe", subject="…", html="…", text="…",
                           idempotency_key=f"reminder:bath:{order_id}", template="reminder_bath", user_id=…)

- La misma `idempotency_key` no se envía dos veces: devuelve el registro existente (esté como esté).
- Nunca lanza por fallas del proveedor o de configuración: queda `FAILED` con `error` en el registro, y las fallas
  temporales se reintentan solas (`retry_due_emails`, cada pocos minutos desde el scheduler).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from app.core.crypto import CryptoUnavailable, decrypt_secret
from app.modules.messaging.domain.email import (
    EMAIL_CHANNEL,
    BaseEmailProvider,
    EmailMessage,
    EmailProviderError,
    Sender,
)
from app.modules.messaging.domain.logs import FAILED, PENDING, SENT, next_attempt_at
from app.modules.messaging.infra.factory import build_email_provider
from app.modules.messaging.infra.models import NotificationLogModel, utcnow

logger = logging.getLogger(__name__)


def _message_payload(message: EmailMessage) -> dict:
    return {"to": message.to, "html": message.html, "text": message.text, "tags": message.tags}


def _message_from(log: NotificationLogModel) -> EmailMessage:
    p = log.payload or {}
    return EmailMessage(to=p.get("to") or [log.recipient], subject=log.subject or "", html=p.get("html"),
                        text=p.get("text"), tags=p.get("tags") or {})


@dataclass
class EmailSender:
    channels: Any       # PostgresChannelRepository
    logs: Any           # PostgresLogRepository
    provider_factory: Callable[[str, str], BaseEmailProvider] = build_email_provider
    now: Callable[[], datetime] = utcnow

    async def send(self, message: EmailMessage, *, idempotency_key: str, template: Optional[str] = None,
                   user_id: Optional[UUID] = None, order_id: Optional[UUID] = None,
                   campaign_id: Optional[UUID] = None, ignore_disabled: bool = False) -> NotificationLogModel:
        existing = await self.logs.get_by_key(idempotency_key)
        if existing is not None:
            return existing
        now = self.now()
        log = NotificationLogModel(
            id=uuid4(), channel=EMAIL_CHANNEL, idempotency_key=idempotency_key, recipient=", ".join(message.to)[:254],
            template=template, subject=message.subject[:300], payload=_message_payload(message), status=PENDING,
            retryable=False, attempts=0, user_id=user_id, order_id=order_id, campaign_id=campaign_id,
            created_at=now, updated_at=now,
        )
        log, created = await self.logs.add(log)
        if not created:
            return log
        return await self.deliver(log, ignore_disabled=ignore_disabled)

    async def deliver(self, log: NotificationLogModel, *, ignore_disabled: bool = False) -> NotificationLogModel:
        """Un intento de envío del registro. Deja el resultado en el registro y lo guarda."""
        config = await self.channels.get(EMAIL_CHANNEL)
        if config is None or not config.secret_encrypted or not config.from_email:
            return await self._fail(log, "El correo no está configurado (Configuración → Integraciones).")
        if not config.is_enabled and not ignore_disabled:
            return await self._fail(log, "El envío de correos está desactivado.")
        try:
            api_key = decrypt_secret(config.secret_encrypted)
        except CryptoUnavailable as exc:
            return await self._fail(log, str(exc))

        log.provider = config.provider
        log.attempts += 1
        log.status = PENDING
        log.updated_at = self.now()
        await self.logs.save(log)  # marca el intento antes de llamar al proveedor (si se cae, queda PENDING)
        sender = Sender(from_email=config.from_email, from_name=config.from_name, reply_to=config.reply_to)
        try:
            provider = self.provider_factory(config.provider, api_key)
            result = await provider.send(_message_from(log), sender=sender, idempotency_key=log.idempotency_key)
        except EmailProviderError as exc:
            return await self._fail(log, exc.message, retryable=exc.retryable)
        except Exception as exc:  # no se sabe si salió: se reintenta con la misma idempotency_key
            logger.exception("Envío de correo %s falló de forma inesperada", log.id)
            return await self._fail(log, f"Error inesperado: {exc.__class__.__name__}.", retryable=True)

        now = self.now()
        log.status = SENT
        log.provider_message_id = result.provider_message_id
        log.error = None
        log.retryable = False
        log.next_attempt_at = None
        log.sent_at = now
        log.updated_at = now
        return await self.logs.save(log)

    async def _fail(self, log: NotificationLogModel, error: str, *, retryable: bool = False) -> NotificationLogModel:
        now = self.now()
        retry_at = next_attempt_at(log.attempts, now=now) if retryable else None
        log.status = FAILED
        log.error = error[:500]
        log.retryable = retry_at is not None
        log.next_attempt_at = retry_at
        log.updated_at = now
        return await self.logs.save(log)

    async def retry_due(self, *, limit: int = 50) -> int:
        due = await self.logs.due_retries(now=self.now(), limit=limit)
        for log in due:
            await self.deliver(log, ignore_disabled=log.template == "test")
        return len(due)


def email_sender(session, **kw) -> EmailSender:
    from app.modules.messaging.infra.postgres_channel_repository import PostgresChannelRepository
    from app.modules.messaging.infra.postgres_log_repository import PostgresLogRepository

    return EmailSender(channels=PostgresChannelRepository(session=session),
                       logs=PostgresLogRepository(session=session), **kw)


async def send_email(session, *, to: str | list[str], subject: str, idempotency_key: str, html: Optional[str] = None,
                     text: Optional[str] = None, tags: Optional[dict[str, str]] = None, template: Optional[str] = None,
                     user_id: Optional[UUID] = None, order_id: Optional[UUID] = None,
                     campaign_id: Optional[UUID] = None) -> NotificationLogModel:
    """Envía (o devuelve el envío ya registrado con esa clave). Ver el docstring del módulo."""
    message = EmailMessage(to=[to] if isinstance(to, str) else list(to), subject=subject, html=html, text=text,
                           tags=tags or {})
    return await email_sender(session).send(message, idempotency_key=idempotency_key, template=template,
                                            user_id=user_id, order_id=order_id, campaign_id=campaign_id)


async def retry_due_emails_job() -> None:
    """Scheduler: reintenta las fallas temporales vencidas y los PENDING colgados."""
    from app.core.db import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            retried = await email_sender(session).retry_due()
            if retried:
                logger.info("retry_due_emails_job retried=%s", retried)
    except Exception:
        logger.exception("retry_due_emails_job failed")
