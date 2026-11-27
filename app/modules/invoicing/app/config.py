"""Configuración de Intifact (feature 0023): leer (secretos enmascarados), guardar, probar la conexión y armar el
cliente con el que se emite."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from fastapi import HTTPException

from app.core.crypto import CryptoUnavailable, decrypt_secret, encrypt_secret, encryption_ready, mask_secret
from app.modules.invoicing.domain.intifact import (
    DEFAULT_BASE_URL,
    DEFAULT_ISSUE_TRIGGER,
    ISSUE_TRIGGERS,
    PROVIDER,
    InvoicingInvalid,
    check_api_key,
    check_ruc,
    check_secret,
    environment_of,
)
from app.modules.invoicing.infra.intifact_client import IntifactClient, IntifactError
from app.modules.invoicing.infra.models import InvoicingProviderModel, utcnow

ClientFactory = Callable[[str, str], IntifactClient]


def invalid(exc: InvoicingInvalid) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": "INVOICING_INVALID", "message": exc.message,
                                                  "field": exc.field})


def no_encryption(exc: CryptoUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail={"code": "ENCRYPTION_UNAVAILABLE", "message": str(exc)})


def not_configured(message: str = "La facturación electrónica no está configurada (Configuración → Integraciones "
                                  "→ Intifact).") -> HTTPException:
    return HTTPException(status_code=409, detail={"code": "INVOICING_NOT_CONFIGURED", "message": message})


@dataclass(frozen=True)
class IntifactIntegration:
    enabled: bool
    configured: bool                 # tiene API key y RUC emisor
    api_url: str
    api_key_mask: Optional[str]
    environment: Optional[str]       # test | live según la key; None sin key
    company_ruc: Optional[str]
    webhook_secret_mask: Optional[str]
    auto_issue: bool
    issue_trigger: str               # service (al realizarse el servicio) | payment (al confirmarse el pago)
    email_customer: bool
    status: str                      # not_configured | disabled | active | error (falló la última prueba)
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


def _view(model: Optional[InvoicingProviderModel]) -> IntifactIntegration:
    if model is None:
        return IntifactIntegration(
            enabled=False, configured=False, api_url=DEFAULT_BASE_URL, api_key_mask=None, environment=None,
            company_ruc=None, webhook_secret_mask=None, auto_issue=False, issue_trigger=DEFAULT_ISSUE_TRIGGER,
            email_customer=True, status="not_configured", last_test_at=None, last_test_ok=None, last_test_error=None,
            encryption_ready=encryption_ready(), updated_at=None, updated_by=None)
    configured = bool(model.token_encrypted and model.company_ruc)
    if not configured:
        status = "not_configured"
    elif not model.is_enabled:
        status = "disabled"
    elif model.last_test_ok is False:
        status = "error"
    else:
        status = "active"
    mask = model.token_mask
    return IntifactIntegration(
        enabled=model.is_enabled, configured=configured, api_url=model.api_url or DEFAULT_BASE_URL,
        api_key_mask=mask, environment=("live" if (mask or "").startswith("fact_live") else "test") if mask else None,
        company_ruc=model.company_ruc, webhook_secret_mask=model.webhook_secret_mask, auto_issue=model.auto_issue,
        issue_trigger=_trigger(model), email_customer=model.email_customer, status=status, last_test_at=model.last_test_at,
        last_test_ok=model.last_test_ok, last_test_error=model.last_test_error, encryption_ready=encryption_ready(),
        updated_at=model.updated_at, updated_by=model.updated_by)


def _trigger(model: Optional[InvoicingProviderModel]) -> str:
    value = model.issue_trigger if model is not None else None
    return value if value in ISSUE_TRIGGERS else DEFAULT_ISSUE_TRIGGER


async def current_issue_trigger(repo) -> str:
    """Momento en que una orden queda lista para emitir (por defecto, al realizarse el servicio)."""
    return _trigger(await repo.get(PROVIDER))


def _mask_key(key: str) -> str:
    """`fact_live_…9aXz`: el prefijo dice el ambiente; nunca la key completa."""
    prefix = "fact_live_" if key.startswith("fact_live_") else "fact_test_"
    return f"{prefix}…{key[-4:]}"


@dataclass
class GetIntifactIntegration:
    repo: Any

    async def execute(self) -> IntifactIntegration:
        return _view(await self.repo.get(PROVIDER))


@dataclass
class UpdateIntifactIntegration:
    repo: Any

    async def execute(self, *, enabled: bool, api_key: Optional[str], company_ruc: Optional[str],
                      webhook_secret: Optional[str], auto_issue: bool, email_customer: bool,
                      actor_id: UUID, issue_trigger: Optional[str] = None) -> IntifactIntegration:
        """Secretos vacíos o ausentes conservan los guardados; sin `issue_trigger`, se conserva el momento de emisión.
        Todo o nada."""
        model = await self.repo.get(PROVIDER)
        try:
            new_key = check_api_key(api_key) if api_key and api_key.strip() else None
            ruc = check_ruc(company_ruc) if company_ruc and company_ruc.strip() else None
            new_secret = check_secret(webhook_secret) if webhook_secret and webhook_secret.strip() else None
            has_key = new_key is not None or bool(model and model.token_encrypted)
            if enabled and not has_key:
                raise InvoicingInvalid("api_key", "Para activar Intifact falta la API key.")
            if enabled and not ruc:
                raise InvoicingInvalid("company_ruc", "Para activar Intifact falta el RUC emisor.")
            if issue_trigger is not None and issue_trigger not in ISSUE_TRIGGERS:
                raise InvoicingInvalid("issue_trigger", "El momento de emisión es service (al realizarse el servicio) "
                                                        "o payment (al confirmarse el pago).")
        except InvoicingInvalid as exc:
            raise invalid(exc) from exc

        if model is None:
            model = InvoicingProviderModel(provider=PROVIDER, api_url=DEFAULT_BASE_URL)
        changed = new_key is not None or model.company_ruc != ruc
        try:
            if new_key is not None:
                model.token_encrypted = encrypt_secret(new_key)
                model.token_mask = _mask_key(new_key)
            if new_secret is not None:
                model.webhook_secret_encrypted = encrypt_secret(new_secret)
                model.webhook_secret_mask = mask_secret(new_secret)
        except CryptoUnavailable as exc:
            raise no_encryption(exc) from exc
        model.is_enabled = enabled
        model.company_ruc = ruc
        model.api_url = model.api_url or DEFAULT_BASE_URL
        model.auto_issue = auto_issue
        model.issue_trigger = issue_trigger or _trigger(model)
        model.email_customer = email_customer
        if changed:  # la última prueba ya no dice nada de la configuración nueva
            model.last_test_at = model.last_test_ok = model.last_test_error = None
        model.updated_by = actor_id
        model.updated_at = utcnow()
        return _view(await self.repo.save(model))


@dataclass(frozen=True)
class ActiveIntifact:
    """Lo necesario para emitir: cliente, RUC emisor, ambiente y URL base."""
    client: IntifactClient
    ruc: str
    environment: str
    base_url: str
    auto_issue: bool
    email_customer: bool
    issue_trigger: str = DEFAULT_ISSUE_TRIGGER


async def active_intifact(repo, client_factory: ClientFactory = IntifactClient, *,
                          require_enabled: bool = True) -> ActiveIntifact:
    model = await repo.get(PROVIDER)
    if model is None or not model.token_encrypted or not model.company_ruc:
        raise not_configured()
    if require_enabled and not model.is_enabled:
        raise not_configured("La facturación electrónica está desactivada (Configuración → Integraciones → Intifact).")
    try:
        key = decrypt_secret(model.token_encrypted)
    except CryptoUnavailable as exc:
        raise no_encryption(exc) from exc
    base_url = model.api_url or DEFAULT_BASE_URL
    return ActiveIntifact(client=client_factory(base_url, key), ruc=model.company_ruc,
                          environment=environment_of(key), base_url=base_url, auto_issue=model.auto_issue,
                          email_customer=model.email_customer, issue_trigger=_trigger(model))


async def webhook_secret(repo) -> Optional[str]:
    model = await repo.get(PROVIDER)
    if model is None or not model.webhook_secret_encrypted:
        return None
    try:
        return decrypt_secret(model.webhook_secret_encrypted)
    except CryptoUnavailable:
        return None


async def current_environment(repo) -> str:
    """Ambiente de la key guardada (test sin key). Las series y los reportes cuentan solo este ambiente."""
    model = await repo.get(PROVIDER)
    return "live" if model is not None and (model.token_mask or "").startswith("fact_live") else "test"


@dataclass
class CheckIntifactConnection:
    """Lista las empresas de la cuenta: no emite nada. Correcto si la key funciona y el RUC emisor está en ella."""
    repo: Any
    client_factory: ClientFactory = IntifactClient

    async def execute(self) -> ConnectionTest:
        model = await self.repo.get(PROVIDER)
        if model is None or not model.token_encrypted or not model.company_ruc:
            raise not_configured("Primero guarda la API key y el RUC emisor de Intifact.")
        intifact = await active_intifact(self.repo, self.client_factory, require_enabled=False)
        try:
            companies = await intifact.client.companies()
            rucs = {str(c.get("ruc") or c.get("numeroRuc") or c.get("empresaRuc") or "") for c in companies}
            ambiente = "pruebas (SUNAT beta)" if intifact.environment == "test" else "producción"
            if model.company_ruc in rucs:
                result = ConnectionTest(ok=True, message=f"Conexión correcta en {ambiente}: la key funciona y el RUC "
                                                         f"{model.company_ruc} está en la cuenta.")
            elif companies:
                result = ConnectionTest(ok=False, message=f"La key funciona, pero el RUC {model.company_ruc} no está "
                                                          f"en la cuenta ({', '.join(sorted(r for r in rucs if r))}).")
            else:
                result = ConnectionTest(ok=False, message="La key funciona, pero la cuenta no tiene empresas.")
        except IntifactError as exc:
            result = ConnectionTest(ok=False, message=f"Intifact: {exc.detail()}")
        model.last_test_at = utcnow()
        model.last_test_ok = result.ok
        model.last_test_error = None if result.ok else result.message[:500]
        await self.repo.save(model)
        return result


@dataclass(frozen=True)
class Readiness:
    """Datos de Paku que necesita un comprobante, para la vista de la integración."""
    company_ruc: Optional[str]
    company_name: Optional[str]
    company_legal_name: Optional[str]
    igv_percent: float
    customers: int
    customers_with_dni: int
    boleta_series: Optional[str]
    factura_series: Optional[str]


async def invoicing_readiness(session, repo) -> Readiness:
    from app.modules.general_settings.app.use_cases import GetSettings
    from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository

    values = await GetSettings(repo=PostgresSettingsRepository(session=session)).execute()
    total, with_dni = await repo.customers_dni()
    boleta = await repo.active_series("03")
    factura = await repo.active_series("01")
    return Readiness(company_ruc=values.get("company_ruc"), company_name=values.get("company_name"),
                     company_legal_name=values.get("company_legal_name"),
                     igv_percent=float(values.get("igv_percent") or 0), customers=total, customers_with_dni=with_dni,
                     boleta_series=boleta.series if boleta else None, factura_series=factura.series if factura else None)
