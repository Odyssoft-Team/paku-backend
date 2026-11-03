"""Facturación electrónica (feature 0020): configuración de Nubefact y prueba de conexión. Solo admin."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.modules.invoicing.api.schemas import (
    ConnectionTestOut,
    NubefactIntegrationIn,
    NubefactIntegrationOut,
    ReadinessOut,
)
from app.modules.invoicing.app.use_cases import (
    CheckNubefactConnection,
    GetNubefactIntegration,
    NubefactIntegration,
    UpdateNubefactIntegration,
    invoicing_readiness,
)
from app.modules.invoicing.infra.postgres_invoicing_repository import PostgresInvoicingRepository

admin_router = APIRouter(tags=["invoicing-admin"])


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresInvoicingRepository:
    return PostgresInvoicingRepository(session=session)


async def _out(view: NubefactIntegration, session, repo) -> NubefactIntegrationOut:
    readiness = await invoicing_readiness(session, repo)
    return NubefactIntegrationOut(**asdict(view), readiness=ReadinessOut(**asdict(readiness)))


@admin_router.get("/integrations/nubefact", response_model=NubefactIntegrationOut)
async def get_nubefact_integration(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    session: AsyncSession = Depends(get_async_session),
) -> NubefactIntegrationOut:
    """Configuración de Nubefact (token enmascarado) y datos de Paku que necesita una boleta (`readiness`)."""
    return await _out(await GetNubefactIntegration(repo=repo).execute(), session, repo)


@admin_router.put("/integrations/nubefact", response_model=NubefactIntegrationOut)
async def update_nubefact_integration(
    payload: NubefactIntegrationIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    session: AsyncSession = Depends(get_async_session),
) -> NubefactIntegrationOut:
    """
    Guarda ruta, token (cifrado; vacío conserva el guardado), serie de boletas y activo. 422
    `INVOICING_CONFIG_INVALID` con `field` (no guarda nada); 503 `ENCRYPTION_UNAVAILABLE` sin llave en el servidor.
    """
    view = await UpdateNubefactIntegration(repo=repo).execute(
        enabled=payload.enabled, api_url=payload.api_url, token=payload.token, boleta_series=payload.boleta_series,
        actor_id=current.id,
    )
    return await _out(view, session, repo)


@admin_router.post("/integrations/nubefact/test", response_model=ConnectionTestOut)
async def test_nubefact_connection(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInvoicingRepository = Depends(get_repo),
) -> ConnectionTestOut:
    """
    Prueba la ruta y el token consultando una boleta que no existe: **no emite nada**. Responde 200 con `ok` y el
    motivo; queda como última prueba. 409 `INVOICING_NOT_CONFIGURED` sin ruta o token.
    """
    return ConnectionTestOut(**asdict(await CheckNubefactConnection(repo=repo).execute()))
