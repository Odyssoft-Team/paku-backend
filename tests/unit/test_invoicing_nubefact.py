"""Feature 0020: configuración de Nubefact (token cifrado y enmascarado), validaciones y prueba de conexión sin emitir.
SQLite en memoria; Nubefact simulado con httpx.MockTransport (sin red)."""
import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import crypto
from app.core.base import Base
from app.core.settings import settings
from app.modules.iam.infra.models import UserModel
from app.modules.invoicing.app.use_cases import (
    CheckNubefactConnection,
    GetNubefactIntegration,
    UpdateNubefactIntegration,
)
from app.modules.invoicing.infra.models import InvoicingProviderModel
from app.modules.invoicing.infra.nubefact_client import NubefactClient
from app.modules.invoicing.infra.postgres_invoicing_repository import PostgresInvoicingRepository

ADMIN = uuid4()
ROUTE = "https://api.nubefact.com/api/v1/03989d1a-6c8c-4b71-b1cd-7d37001deaa0"
TOKEN = "d0a80b88cde446d092025465bdb4673e103a0d881ca6479ebbab10664dbc5677"
T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())


async def _with_repo(fn):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all,
                            tables=[InvoicingProviderModel.__table__, UserModel.__table__])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        return await fn(PostgresInvoicingRepository(session=session), session)
    finally:
        await session.close()
        await engine.dispose()


def _run(fn):
    return asyncio.run(_with_repo(fn))


def _update(repo, **kw):
    data = dict(enabled=False, api_url=None, token=None, boleta_series=None)
    data.update(kw)
    return UpdateNubefactIntegration(repo=repo).execute(**data, actor_id=ADMIN)


def test_save_encrypts_masks_and_keeps_token():
    async def scenario(repo, _):
        empty = await GetNubefactIntegration(repo=repo).execute()
        assert (empty.status, empty.boleta_series, empty.token_mask) == ("not_configured", "B001", None)

        view = await _update(repo, enabled=True, api_url=f" {ROUTE}/ ", token=TOKEN, boleta_series="b002")
        assert (view.status, view.api_url, view.boleta_series, view.token_mask) == (
            "active", ROUTE, "B002", "d0a80…5677")
        stored = await repo.get("nubefact")
        assert TOKEN not in stored.token_encrypted and crypto.decrypt_secret(stored.token_encrypted) == TOKEN

        view = await _update(repo, enabled=False, api_url=ROUTE, token="", boleta_series="B002")
        assert (view.status, view.token_mask) == ("disabled", "d0a80…5677")
    _run(scenario)


@pytest.mark.parametrize("kw,field", [
    (dict(enabled=True, token=TOKEN), "api_url"),
    (dict(enabled=True, api_url=ROUTE), "token"),
    (dict(api_url="http://api.nubefact.com/api/v1/x"), "api_url"),        # http solo en localhost
    (dict(api_url="https://api.nubefact.com"), "api_url"),                # falta el identificador
    (dict(api_url="nubefact"), "api_url"),
    (dict(api_url=ROUTE, boleta_series="F001"), "boleta_series"),         # F es de facturas
    (dict(api_url=ROUTE, boleta_series="B01"), "boleta_series"),
    (dict(api_url=ROUTE, token="con espacio"), "token"),
])
def test_invalid_config_saves_nothing(kw, field):
    async def scenario(repo, _):
        with pytest.raises(HTTPException) as exc:
            await _update(repo, **kw)
        assert exc.value.status_code == 422
        assert exc.value.detail == {**exc.value.detail, "code": "INVOICING_CONFIG_INVALID", "field": field}
        assert await repo.get("nubefact") is None
    _run(scenario)


def test_offline_localhost_route_is_allowed():
    async def scenario(repo, _):
        view = await _update(repo, api_url="http://localhost:8000/api/v1/abc", token=TOKEN)
        assert view.api_url == "http://localhost:8000/api/v1/abc"
    _run(scenario)


def _client(handler, seen):
    def factory(url, token):
        seen.append((url, token))
        return NubefactClient(url, token, transport=httpx.MockTransport(handler))
    return factory


@pytest.mark.parametrize("status,body,ok,message", [
    (400, {"errors": "El documento no existe", "codigo": 24}, True, "Conexión correcta"),
    (401, {"errors": "Token incorrecto", "codigo": 10}, False, "El token es incorrecto o fue eliminado."),
    (400, {"errors": "Ruta incorrecta", "codigo": 11}, False, "La ruta (URL) es incorrecta o no existe."),
    (400, {"errors": "Cuenta suspendida", "codigo": 51}, False, "suspendida por falta de pago"),
    (500, {}, False, "Nubefact respondió 500."),
])
def test_connection_test_does_not_issue(status, body, ok, message):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json=body)

    async def scenario(repo, _):
        with pytest.raises(HTTPException) as exc:
            await CheckNubefactConnection(repo=repo).execute()
        assert exc.value.detail["code"] == "INVOICING_NOT_CONFIGURED"

        await _update(repo, enabled=True, api_url=ROUTE, token=TOKEN, boleta_series="B001")
        seen = []
        result = await CheckNubefactConnection(repo=repo, client_factory=_client(handler, seen)).execute()
        assert result.ok is ok and message in result.message
        assert seen == [(ROUTE, TOKEN)]
        sent = json.loads(requests[0].content)
        assert sent == {"operacion": "consultar_comprobante", "tipo_de_comprobante": 2, "serie": "B001",
                        "numero": 99999999}                            # solo consulta: nunca generar_comprobante
        assert requests[0].headers["authorization"] == TOKEN          # sin «Bearer», como el manual
        view = await GetNubefactIntegration(repo=repo).execute()
        assert (view.last_test_ok, view.status) == (ok, "active" if ok else "error")
    _run(scenario)


def test_connection_unreachable():
    def handler(request):
        raise httpx.ConnectError("sin red")

    async def scenario(repo, _):
        await _update(repo, api_url=ROUTE, token=TOKEN)
        result = await CheckNubefactConnection(repo=repo, client_factory=_client(handler, [])).execute()
        assert (result.ok, result.message) == (False, "No se pudo conectar con Nubefact: ConnectError.")
    _run(scenario)


def test_customers_with_dni():
    async def scenario(repo, session):
        for dni, role, active in [("12345678", "user", True), (None, "user", True), ("  ", "user", True),
                                  ("87654321", "user", False), ("11112222", "admin", True)]:
            session.add(UserModel(id=uuid4(), email=f"{uuid4().hex[:8]}@correo.pe", role=role, is_active=active,
                                  dni=dni, first_name="Ana", last_name="Pérez", created_at=T0, updated_at=T0))
        await session.commit()
        assert await repo.customers_dni() == (3, 1)
    _run(scenario)
