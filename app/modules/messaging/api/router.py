"""Integraciones de envío (feature 0018): configuración del correo saliente. Solo admin."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.modules.messaging.api.schemas import (
    EmailIntegrationIn,
    EmailIntegrationOut,
    NotificationLogOut,
    NotificationLogPageOut,
    ProviderOptionOut,
    TestEmailIn,
    TestEmailOut,
)
from app.modules.messaging.app.use_cases import (
    EmailIntegration,
    GetEmailIntegration,
    ListNotificationLogs,
    RetryNotificationLog,
    SendTestEmail,
    UpdateEmailIntegration,
)
from app.modules.messaging.domain.email import EMAIL_PROVIDERS
from app.modules.messaging.infra.postgres_channel_repository import PostgresChannelRepository
from app.modules.messaging.infra.postgres_log_repository import PostgresLogRepository

admin_router = APIRouter(tags=["integrations-admin"])


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresChannelRepository:
    return PostgresChannelRepository(session=session)


def get_logs(session: AsyncSession = Depends(get_async_session)) -> PostgresLogRepository:
    return PostgresLogRepository(session=session)


def _out(view: EmailIntegration) -> EmailIntegrationOut:
    return EmailIntegrationOut(**asdict(view),
                               providers=[ProviderOptionOut(value=k, label=v) for k, v in EMAIL_PROVIDERS.items()])


@admin_router.get("/integrations/email", response_model=EmailIntegrationOut)
async def get_email_integration(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresChannelRepository = Depends(get_repo),
) -> EmailIntegrationOut:
    """Configuración del correo saliente. La API key nunca se devuelve completa (`api_key_mask`)."""
    return _out(await GetEmailIntegration(repo=repo).execute())


@admin_router.put("/integrations/email", response_model=EmailIntegrationOut)
async def update_email_integration(
    payload: EmailIntegrationIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresChannelRepository = Depends(get_repo),
) -> EmailIntegrationOut:
    """
    Guarda la configuración. `api_key` vacía o ausente conserva la guardada; se cifra antes de guardarla.
    422 `EMAIL_CONFIG_INVALID` con `field` (no guarda nada); 503 `ENCRYPTION_UNAVAILABLE` si el servidor no tiene
    `CREDENTIALS_ENCRYPTION_KEY`.
    """
    view = await UpdateEmailIntegration(repo=repo).execute(
        provider=payload.provider, enabled=payload.enabled, api_key=payload.api_key, from_email=payload.from_email,
        from_name=payload.from_name, reply_to=payload.reply_to, actor_id=current.id,
    )
    return _out(view)


@admin_router.post("/integrations/email/test", response_model=TestEmailOut)
async def send_test_email(
    payload: TestEmailIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresChannelRepository = Depends(get_repo),
    logs: PostgresLogRepository = Depends(get_logs),
) -> TestEmailOut:
    """
    Envía un correo de prueba con lo guardado (aunque esté desactivado). Si el proveedor lo rechaza responde 200 con
    `ok: false` y `error`, y queda como última prueba. 409 `EMAIL_NOT_CONFIGURED` sin API key o remitente.
    También queda en el registro de envíos (`template: "test"`).
    """
    result = await SendTestEmail(repo=repo, logs=logs).execute(to=payload.to or current.email, actor_id=current.id)
    return TestEmailOut(**asdict(result))


@admin_router.get("/notification-logs", response_model=NotificationLogPageOut)
async def list_notification_logs(
    channel: Optional[str] = Query(None, description="email"),
    status: Optional[str] = Query(None, description="PENDING | SENT | FAILED"),
    q: Optional[str] = Query(None, description="Destinatario o asunto"),
    date_from: Optional[date] = Query(None, description="Día de creación (hora de Lima), incluido"),
    date_to: Optional[date] = Query(None, description="Día de creación (hora de Lima), incluido"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: CurrentUser = Depends(require_roles("admin")),
    logs: PostgresLogRepository = Depends(get_logs),
) -> NotificationLogPageOut:
    """Registro de envíos, más recientes primero. `counts` por estado ignora el filtro `status`.
    422 `LOG_STATUS_INVALID` / `DATE_RANGE_INVALID`."""
    page = await ListNotificationLogs(logs=logs).execute(channel=channel, status=status, q=q, date_from=date_from,
                                                         date_to=date_to, limit=limit, offset=offset)
    return NotificationLogPageOut(items=[NotificationLogOut.model_validate(i) for i in page.items],
                                  total=page.total, counts=page.counts)


@admin_router.post("/notification-logs/{log_id}/retry", response_model=NotificationLogOut)
async def retry_notification_log(
    log_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresChannelRepository = Depends(get_repo),
    logs: PostgresLogRepository = Depends(get_logs),
) -> NotificationLogOut:
    """Reintenta ahora un envío `FAILED`. 404 `LOG_NOT_FOUND`; 409 `LOG_NOT_RETRYABLE` si no está fallido."""
    return NotificationLogOut.model_validate(await RetryNotificationLog(repo=repo, logs=logs).execute(log_id))
