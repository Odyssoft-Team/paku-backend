"""Configuración de Nubefact (feature 0020): leer (token enmascarado), guardar y probar la conexión sin emitir."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from fastapi import HTTPException

from app.core.crypto import CryptoUnavailable, decrypt_secret, encrypt_secret, encryption_ready, mask_secret
from app.modules.invoicing.domain.nubefact import (
    DEFAULT_BOLETA_SERIES,
    DOCUMENT_NOT_FOUND,
    PROBE_NUMBER,
    PROVIDER,
    InvoicingConfigInvalid,
    check_token,
    error_message,
    normalize_route,
    normalize_series,
)
from app.modules.invoicing.infra.models import InvoicingProviderModel, utcnow
from app.modules.invoicing.infra.nubefact_client import NubefactClient, NubefactUnreachable


@dataclass(frozen=True)
class NubefactIntegration:
    enabled: bool
    configured: bool                 # tiene ruta, token y serie
    api_url: Optional[str]
    token_mask: Optional[str]
    boleta_series: str
    status: str                      # not_configured | disabled | active | error
    last_test_at: Optional[datetime]
    last_test_ok: Optional[bool]
    last_test_error: Optional[str]
    encryption_ready: bool
    updated_at: Optional[datetime]
    updated_by: Optional[UUID]


@dataclass(frozen=True)
class ConnectionTest:
    ok: bool
    message: str


def _invalid(exc: InvoicingConfigInvalid) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": "INVOICING_CONFIG_INVALID", "message": exc.message,
                                                  "field": exc.field})


def _no_encryption(exc: CryptoUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail={"code": "ENCRYPTION_UNAVAILABLE", "message": str(exc)})


def _view(model: Optional[InvoicingProviderModel]) -> NubefactIntegration:
    if model is None:
        return NubefactIntegration(enabled=False, configured=False, api_url=None, token_mask=None,
                                   boleta_series=DEFAULT_BOLETA_SERIES, status="not_configured", last_test_at=None,
                                   last_test_ok=None, last_test_error=None, encryption_ready=encryption_ready(),
                                   updated_at=None, updated_by=None)
    configured = bool(model.api_url and model.token_encrypted and model.boleta_series)
    if not configured:
        status = "not_configured"
    elif not model.is_enabled:
        status = "disabled"
    elif model.last_test_ok is False:
        status = "error"
    else:
        status = "active"
    return NubefactIntegration(
        enabled=model.is_enabled, configured=configured, api_url=model.api_url, token_mask=model.token_mask,
        boleta_series=model.boleta_series or DEFAULT_BOLETA_SERIES, status=status, last_test_at=model.last_test_at,
        last_test_ok=model.last_test_ok, last_test_error=model.last_test_error, encryption_ready=encryption_ready(),
        updated_at=model.updated_at, updated_by=model.updated_by,
    )


@dataclass
class GetNubefactIntegration:
    repo: Any

    async def execute(self) -> NubefactIntegration:
        return _view(await self.repo.get(PROVIDER))


@dataclass
class UpdateNubefactIntegration:
    repo: Any

    async def execute(self, *, enabled: bool, api_url: Optional[str], token: Optional[str],
                      boleta_series: Optional[str], actor_id: UUID) -> NubefactIntegration:
        """`token` vacío o ausente conserva el guardado. Todo o nada."""
        model = await self.repo.get(PROVIDER)
        try:
            route = normalize_route(api_url) if api_url and api_url.strip() else None
            new_token = check_token(token) if token and token.strip() else None
            series = normalize_series(boleta_series) if boleta_series and boleta_series.strip() else DEFAULT_BOLETA_SERIES
            has_token = new_token is not None or bool(model and model.token_encrypted)
            if enabled and not route:
                raise InvoicingConfigInvalid("api_url", "Para activar Nubefact falta la ruta.")
            if enabled and not has_token:
                raise InvoicingConfigInvalid("token", "Para activar Nubefact falta el token.")
        except InvoicingConfigInvalid as exc:
            raise _invalid(exc) from exc

        if model is None:
            model = InvoicingProviderModel(provider=PROVIDER)
        changed = new_token is not None or model.api_url != route or model.boleta_series != series
        if new_token is not None:
            try:
                model.token_encrypted = encrypt_secret(new_token)
            except CryptoUnavailable as exc:
                raise _no_encryption(exc) from exc
            model.token_mask = mask_secret(new_token)
        model.is_enabled = enabled
        model.api_url = route
        model.boleta_series = series
        if changed:  # la última prueba ya no dice nada de la configuración nueva
            model.last_test_at = model.last_test_ok = model.last_test_error = None
        model.updated_by = actor_id
        model.updated_at = utcnow()
        return _view(await self.repo.save(model))


@dataclass
class CheckNubefactConnection:
    """Consulta una boleta que no existe (serie configurada, n.º 99999999): no emite nada.

    «No existe» (código 24) o una respuesta correcta = la ruta y el token funcionan. Token o ruta mal (10, 11),
    cuenta suspendida (50, 51) u otro error = falla, con el motivo.
    """
    repo: Any
    client_factory: Callable[[str, str], NubefactClient] = NubefactClient

    async def execute(self) -> ConnectionTest:
        model = await self.repo.get(PROVIDER)
        if model is None or not model.api_url or not model.token_encrypted:
            raise HTTPException(status_code=409, detail={
                "code": "INVOICING_NOT_CONFIGURED", "message": "Primero guarda la ruta y el token de Nubefact."})
        try:
            token = decrypt_secret(model.token_encrypted)
        except CryptoUnavailable as exc:
            raise _no_encryption(exc) from exc

        client = self.client_factory(model.api_url, token)
        try:
            r = await client.consultar_boleta(serie=model.boleta_series or DEFAULT_BOLETA_SERIES, numero=PROBE_NUMBER)
            if r.codigo == DOCUMENT_NOT_FOUND or (r.status_code == 200 and r.codigo is None):
                result = ConnectionTest(ok=True, message="Conexión correcta: la ruta y el token son válidos.")
            else:
                result = ConnectionTest(ok=False, message=error_message(r.codigo, r.errors)
                                        if (r.codigo or r.errors) else f"Nubefact respondió {r.status_code}.")
        except NubefactUnreachable as exc:
            result = ConnectionTest(ok=False, message=str(exc))
        model.last_test_at = utcnow()
        model.last_test_ok = result.ok
        model.last_test_error = None if result.ok else result.message[:500]
        await self.repo.save(model)
        return result


@dataclass(frozen=True)
class Readiness:
    """Datos de Paku que necesita una boleta, para la vista de capacidades."""
    company_ruc: Optional[str]
    company_name: Optional[str]
    igv_percent: float
    customers: int
    customers_with_dni: int


async def invoicing_readiness(session, repo) -> Readiness:
    from app.modules.general_settings.app.use_cases import GetSettings
    from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository

    values = await GetSettings(repo=PostgresSettingsRepository(session=session)).execute()
    total, with_dni = await repo.customers_dni()
    return Readiness(company_ruc=values.get("company_ruc"), company_name=values.get("company_name"),
                     igv_percent=float(values.get("igv_percent") or 0), customers=total, customers_with_dni=with_dni)
