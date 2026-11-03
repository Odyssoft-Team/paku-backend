"""Configuración del correo saliente (feature 0018): leer (credencial enmascarada), guardar y enviar una prueba."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.core.crypto import CryptoUnavailable, decrypt_secret, encrypt_secret, encryption_ready
from app.core.timezone import LIMA_TZ
from app.modules.messaging.app.sender import EmailSender
from app.modules.messaging.domain.email import (
    EMAIL_CHANNEL,
    EMAIL_PROVIDERS,
    FROM_NAME_MAX,
    BaseEmailProvider,
    EmailConfigInvalid,
    EmailMessage,
    check_api_key,
    mask_secret,
    normalize_email,
)
from app.modules.messaging.domain.logs import FAILED, SENT, STATUSES
from app.modules.messaging.infra.factory import build_email_provider
from app.modules.messaging.infra.models import ChannelProviderModel, utcnow

DEFAULT_PROVIDER = "resend"


@dataclass(frozen=True)
class EmailIntegration:
    provider: str
    enabled: bool
    configured: bool                 # tiene API key y remitente
    api_key_mask: Optional[str]
    from_email: Optional[str]
    from_name: Optional[str]
    reply_to: Optional[str]
    status: str                      # not_configured | disabled | active | error
    last_test_at: Optional[datetime]
    last_test_ok: Optional[bool]
    last_test_error: Optional[str]
    encryption_ready: bool
    updated_at: Optional[datetime]
    updated_by: Optional[UUID]


@dataclass(frozen=True)
class TestEmailResult:
    ok: bool
    to: str
    provider_message_id: Optional[str]
    error: Optional[str]


def _invalid(exc: EmailConfigInvalid) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": "EMAIL_CONFIG_INVALID", "message": exc.message,
                                                  "field": exc.field})


def _no_encryption(exc: CryptoUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail={"code": "ENCRYPTION_UNAVAILABLE", "message": str(exc)})


def _view(model: Optional[ChannelProviderModel]) -> EmailIntegration:
    if model is None:
        return EmailIntegration(provider=DEFAULT_PROVIDER, enabled=False, configured=False, api_key_mask=None,
                                from_email=None, from_name=None, reply_to=None, status="not_configured",
                                last_test_at=None, last_test_ok=None, last_test_error=None,
                                encryption_ready=encryption_ready(), updated_at=None, updated_by=None)
    configured = bool(model.secret_encrypted and model.from_email)
    if not configured:
        status = "not_configured"
    elif not model.is_enabled:
        status = "disabled"
    elif model.last_test_ok is False:
        status = "error"
    else:
        status = "active"
    return EmailIntegration(
        provider=model.provider, enabled=model.is_enabled, configured=configured, api_key_mask=model.secret_mask,
        from_email=model.from_email, from_name=model.from_name, reply_to=model.reply_to, status=status,
        last_test_at=model.last_test_at, last_test_ok=model.last_test_ok, last_test_error=model.last_test_error,
        encryption_ready=encryption_ready(), updated_at=model.updated_at, updated_by=model.updated_by,
    )


def _optional_email(value: Optional[str], *, field: str) -> Optional[str]:
    return normalize_email(value, field=field) if value and value.strip() else None


@dataclass
class GetEmailIntegration:
    repo: Any

    async def execute(self) -> EmailIntegration:
        return _view(await self.repo.get(EMAIL_CHANNEL))


@dataclass
class UpdateEmailIntegration:
    repo: Any

    async def execute(self, *, provider: str, enabled: bool, api_key: Optional[str], from_email: Optional[str],
                      from_name: Optional[str], reply_to: Optional[str], actor_id: UUID) -> EmailIntegration:
        """`api_key` vacío o ausente conserva la guardada. Todo o nada."""
        model = await self.repo.get(EMAIL_CHANNEL)
        try:
            if provider not in EMAIL_PROVIDERS:
                raise EmailConfigInvalid("provider", f"Proveedor desconocido: {provider}.")
            new_key = check_api_key(provider, api_key) if api_key and api_key.strip() else None
            has_key = new_key is not None or bool(model and model.secret_encrypted)
            if model and model.provider != provider and model.secret_encrypted and new_key is None:
                raise EmailConfigInvalid("api_key", "Al cambiar de proveedor hay que ingresar su API key.")
            clean_from = _optional_email(from_email, field="from_email")
            clean_reply = _optional_email(reply_to, field="reply_to")
            clean_name = (from_name or "").strip() or None
            if clean_name and len(clean_name) > FROM_NAME_MAX:
                raise EmailConfigInvalid("from_name", f"El nombre del remitente admite hasta {FROM_NAME_MAX} caracteres.")
            if clean_name and any(c in clean_name for c in '<>"'):
                raise EmailConfigInvalid("from_name", "El nombre del remitente no puede tener < > ni comillas.")
            if enabled and not has_key:
                raise EmailConfigInvalid("api_key", "Para activar el correo falta la API key.")
            if enabled and not clean_from:
                raise EmailConfigInvalid("from_email", "Para activar el correo falta el correo del remitente.")
        except EmailConfigInvalid as exc:
            raise _invalid(exc) from exc

        if model is None:
            model = ChannelProviderModel(channel=EMAIL_CHANNEL, provider=provider)
        changed_delivery = (new_key is not None or model.provider != provider or model.from_email != clean_from)
        if new_key is not None:
            try:
                model.secret_encrypted = encrypt_secret(new_key)
            except CryptoUnavailable as exc:
                raise _no_encryption(exc) from exc
            model.secret_mask = mask_secret(new_key)
        model.provider = provider
        model.is_enabled = enabled
        model.from_email = clean_from
        model.from_name = clean_name
        model.reply_to = clean_reply
        if changed_delivery:  # la última prueba ya no dice nada de la configuración nueva
            model.last_test_at = model.last_test_ok = model.last_test_error = None
        model.updated_by = actor_id
        model.updated_at = utcnow()
        return _view(await self.repo.save(model))


TEST_SUBJECT = "Correo de prueba de Paku"
TEST_TEMPLATE = "test"


def _test_message(to: str) -> EmailMessage:
    text = ("Este es un correo de prueba enviado desde el panel de Paku (Configuración → Integraciones).\n"
            "Si lo recibiste, el envío de correos está bien configurado.")
    html = ("<p>Este es un correo de prueba enviado desde el panel de Paku "
            "(Configuración → Integraciones).</p><p>Si lo recibiste, el envío de correos está bien configurado.</p>")
    return EmailMessage(to=[to], subject=TEST_SUBJECT, html=html, text=text, tags={"category": "test"})


@dataclass
class SendTestEmail:
    repo: Any
    logs: Any
    provider_factory: Callable[[str, str], BaseEmailProvider] = build_email_provider

    async def execute(self, *, to: str, actor_id: Optional[UUID] = None) -> TestEmailResult:
        """Envía con lo guardado aunque el correo esté desactivado (para probar antes de activarlo). Queda en el
        registro de envíos como `template="test"`, sin reintentos automáticos (el admin ve el resultado al momento)."""
        try:
            to = normalize_email(to, field="to")
        except EmailConfigInvalid as exc:
            raise _invalid(exc) from exc
        model = await self.repo.get(EMAIL_CHANNEL)
        if model is None or not model.secret_encrypted or not model.from_email:
            raise HTTPException(status_code=409, detail={
                "code": "EMAIL_NOT_CONFIGURED", "message": "Primero guarda la API key y el correo del remitente."})
        try:
            decrypt_secret(model.secret_encrypted)
        except CryptoUnavailable as exc:
            raise _no_encryption(exc) from exc

        sender = EmailSender(channels=self.repo, logs=self.logs, provider_factory=self.provider_factory)
        log = await sender.send(_test_message(to), idempotency_key=f"test:{uuid4()}", template=TEST_TEMPLATE,
                                user_id=actor_id, ignore_disabled=True)
        if log.status == FAILED and log.retryable:
            log.retryable, log.next_attempt_at = False, None
            await self.logs.save(log)
        ok = log.status == SENT
        result = TestEmailResult(ok=ok, to=to, provider_message_id=log.provider_message_id,
                                 error=None if ok else log.error)
        model.last_test_at = utcnow()
        model.last_test_ok = result.ok
        model.last_test_error = result.error
        await self.repo.save(model)
        return result


@dataclass(frozen=True)
class LogPage:
    items: list
    total: int
    counts: dict[str, int]


def _lima_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=LIMA_TZ)


@dataclass
class ListNotificationLogs:
    logs: Any

    async def execute(self, *, channel: Optional[str], status: Optional[str], q: Optional[str],
                      date_from: Optional[date], date_to: Optional[date], limit: int, offset: int) -> LogPage:
        """Fechas = días de creación en hora de Lima, ambos incluidos."""
        if status and status not in STATUSES:
            raise HTTPException(status_code=422, detail={"code": "LOG_STATUS_INVALID",
                                                          "message": f"Estado desconocido: {status}."})
        if date_from and date_to and date_from > date_to:
            raise HTTPException(status_code=422, detail={
                "code": "DATE_RANGE_INVALID", "message": "La fecha desde no puede ser posterior a la fecha hasta."})
        items, total, counts = await self.logs.search(
            channel=channel, status=status, q=(q or "").strip() or None,
            created_from=_lima_start(date_from) if date_from else None,
            created_to=_lima_start(date_to + timedelta(days=1)) if date_to else None,
            limit=limit, offset=offset,
        )
        return LogPage(items=items, total=total, counts={s: counts.get(s, 0) for s in STATUSES})


@dataclass
class RetryNotificationLog:
    repo: Any
    logs: Any
    provider_factory: Callable[[str, str], BaseEmailProvider] = build_email_provider

    async def execute(self, log_id: UUID):
        """Reintento manual de un envío `FAILED` (aunque ya no le queden reintentos automáticos)."""
        log = await self.logs.get(log_id)
        if log is None:
            raise HTTPException(status_code=404, detail={"code": "LOG_NOT_FOUND", "message": "Envío no encontrado."})
        if log.status != FAILED:
            raise HTTPException(status_code=409, detail={
                "code": "LOG_NOT_RETRYABLE", "message": "Solo se reintentan los envíos fallidos."})
        sender = EmailSender(channels=self.repo, logs=self.logs, provider_factory=self.provider_factory)
        return await sender.deliver(log, ignore_disabled=log.template == TEST_TEMPLATE)
