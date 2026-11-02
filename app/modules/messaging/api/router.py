"""Integraciones de envío (feature 0018): configuración del correo saliente. Solo admin."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.modules.messaging.api.schemas import (
    EmailIntegrationIn,
    EmailIntegrationOut,
    ProviderOptionOut,
    TestEmailIn,
    TestEmailOut,
)
from app.modules.messaging.app.use_cases import (
    EmailIntegration,
    GetEmailIntegration,
    SendTestEmail,
    UpdateEmailIntegration,
)
from app.modules.messaging.domain.email import EMAIL_PROVIDERS
from app.modules.messaging.infra.postgres_channel_repository import PostgresChannelRepository

admin_router = APIRouter(tags=["integrations-admin"])


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresChannelRepository:
    return PostgresChannelRepository(session=session)


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
) -> TestEmailOut:
    """
    Envía un correo de prueba con lo guardado (aunque esté desactivado). Si el proveedor lo rechaza responde 200 con
    `ok: false` y `error`, y queda como última prueba. 409 `EMAIL_NOT_CONFIGURED` sin API key o remitente.
    """
    result = await SendTestEmail(repo=repo).execute(to=payload.to or current.email)
    return TestEmailOut(**asdict(result))
