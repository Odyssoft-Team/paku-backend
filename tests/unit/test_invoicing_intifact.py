"""Feature 0023: facturación electrónica con Intifact. SQLite en memoria; Intifact simulado con httpx.MockTransport
(sin red)."""
import asyncio
import hashlib
import hmac
import json
import zipfile
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import crypto
from app.core.base import Base
from app.core.settings import settings
from app.modules.catalog.infra.models import BreedModel
from app.modules.iam.infra.models import UserModel
from app.modules.invoicing.app import accounting
from app.modules.invoicing.app.config import (
    CheckIntifactConnection,
    GetIntifactIntegration,
    UpdateIntifactIntegration,
    active_intifact,
)
from app.modules.invoicing.app.directory import ListDirectory, SaveCompany, SearchCustomers
from app.modules.invoicing.app.documents import (
    CustomerDocuments,
    CustomerInput,
    IssueBatch,
    IssueDocument,
    ListPending,
    ListRegistry,
    RefreshDocument,
    VoidDocument,
    apply_status,
    own_document,
)
from app.modules.invoicing.app.jobs import HandleWebhook, auto_issue, refresh_in_progress
from app.modules.invoicing.app.series import CreateSeries, ListSeries, UpdateSeries
from app.modules.invoicing.domain import intifact as dom
from app.modules.invoicing.infra.intifact_client import IntifactClient
from app.modules.invoicing.infra.models import (
    InvoiceDocumentModel,
    InvoicingCompanyModel,
    InvoicingProviderModel,
    InvoicingSeriesModel,
)
from app.modules.invoicing.infra.postgres_invoicing_repository import PostgresInvoicingRepository
from app.modules.orders.infra.models import OrderModel, OrderPetModel
from app.modules.pets.infra.models import PetModel

ADMIN = uuid4()
KEY = "fact_test_abcdefghijklmnop1234"
RUC_EMISOR = "20615013898"
SECRET = "whsec_secreto_de_prueba"


# ---------- Intifact simulado ----------

class FakeIntifact:
    def __init__(self):
        self.next = 1
        self.sent: list[dict] = []
        self.cancels: list[tuple[str, dict]] = []
        self.status: dict[str, str] = {}
        self.default_status = "ACEPTADO"
        self.compute_offset = Decimal("0")
        self.companies = [{"ruc": RUC_EMISOR, "razonSocial": "SMARTPETSOLUTIONS S.A.C."}]
        self.requests: list[str] = []

    def compute(self, body):
        items, total_all, base_all = [], Decimal("0"), Decimal("0")
        for it in body["items"]:
            qty = Decimal(str(it["cantidad"]))
            price = Decimal(str(it["valorUnitario"]))
            total = (price * qty).quantize(Decimal("0.01"))
            base = (total / Decimal("1.18")).quantize(Decimal("0.01"))
            items.append({"descripcion": it["descripcion"], "cantidad": float(qty), "unidad": it["unidad"],
                          "codProducto": it["codProducto"], "tipAfeIgv": "10", "porcentajeIgv": 18,
                          "montoValorUnitario": float((base / qty).quantize(Decimal("0.01"))),
                          "montoPrecioUnitario": float(price), "montoValorVenta": float(base),
                          "montoBaseIgv": float(base), "igv": float(total - base), "totalImpuestos": float(total - base),
                          "extraQueNoSeEnvia": "x"})
            total_all += total
            base_all += base
        total_all += self.compute_offset
        return {"tipoMoneda": "PEN", "montoOperGravadas": float(base_all), "montoIgv": float(total_all - base_all),
                "totalImpuestos": float(total_all - base_all), "valorVenta": float(base_all),
                "subTotal": float(total_all), "montoImpVenta": float(total_all),
                "montoEnLetras": "SON CIENTO VEINTE CON 00/100 SOLES", "items": items}

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.replace("/api/v1", "")
        self.requests.append(f"{request.method} {path}")
        assert request.headers["Authorization"] == f"Bearer {KEY}"
        ok = lambda data: httpx.Response(200, json={"success": True, "message": "ok", "data": data})  # noqa: E731
        if path == "/companies":
            return ok(self.companies)
        if path == "/invoice/compute":
            return ok(self.compute(json.loads(request.content)))
        if path == "/documents/next-correlativo":
            return ok({"next": self.next})
        if path == "/invoice/send":
            body = json.loads(request.content)
            self.sent.append(body)
            doc_id = f"doc-{len(self.sent)}"
            return httpx.Response(202, json={"success": True, "data": {"id": doc_id, "estado": "ENCOLADO",
                                                                        "hash": "abc"}})
        if path.startswith("/documents/"):
            doc_id = path.split("/")[-1]
            return ok({"id": doc_id, "sunat": {"estado": self.status.get(doc_id, self.default_status),
                                               "codigoRespuesta": "0", "descripcionRespuesta": "aceptado"}})
        if path in ("/invoice/cancel", "/boleta/cancel"):
            self.cancels.append((path, json.loads(request.content)))
            return ok({"ticket": "123"})
        if path.endswith("/pdf"):
            return httpx.Response(200, content=b"%PDF-1.4 fake", headers={"content-type": "application/pdf"})
        if path.endswith("/xml"):
            return httpx.Response(200, content=b"<xml/>", headers={"content-type": "application/xml"})
        return httpx.Response(404, json={"success": False, "message": "no existe"})


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())


TABLES = [InvoicingProviderModel, InvoicingSeriesModel, InvoiceDocumentModel, InvoicingCompanyModel, UserModel,
          OrderModel, OrderPetModel, BreedModel, PetModel]


class Ctx:
    def __init__(self, repo, session, fake):
        self.repo, self.session, self.fake = repo, session, fake
        self.emails: list[dict] = []

    def factory(self, base_url, key):
        return IntifactClient(base_url, key, transport=httpx.MockTransport(self.fake.handler))

    async def intifact(self):
        return await active_intifact(self.repo, self.factory)

    async def notifier(self, **kw):
        self.emails.append(kw)

    async def configure(self, *, auto=False, boleta=True, factura=True, first_number=1):
        await UpdateIntifactIntegration(repo=self.repo).execute(
            enabled=True, api_key=KEY, company_ruc=RUC_EMISOR, webhook_secret=SECRET, auto_issue=auto,
            email_customer=True, actor_id=ADMIN)
        if boleta:
            await CreateSeries(repo=self.repo).execute(tipo="BOLETA", series="B001", first_number=first_number,
                                                        is_active=True)
        if factura:
            await CreateSeries(repo=self.repo).execute(tipo="FACTURA", series="F001", first_number=1, is_active=True)

    async def user(self, dni="45678912", first="Ana", last="Pérez"):
        u = UserModel(email=f"{uuid4().hex[:8]}@correo.pe", role="user", first_name=first, last_name=last, dni=dni)
        return await self.repo.save(u)

    async def order(self, user, *, total=120, items=None, paid=True, status="done", discount=None, parent=None,
                    pet="Toby"):
        items = items or [
            {"kind": "service_base", "ref_id": "s1", "name": "Baño completo", "qty": 1, "unit_price": 100},
            {"kind": "service_addon", "ref_id": "a1", "name": "Corte de uñas", "qty": 1, "unit_price": 20},
        ]
        o = OrderModel(user_id=user.id, status=status, items_snapshot=items, total_snapshot=Decimal(str(total)),
                       payment_status="paid" if paid else "pending", payment_method="card", discount_amount=discount,
                       parent_order_id=parent)
        await self.repo.save(o)
        if pet:
            p = await self.repo.save(PetModel(owner_id=user.id, name=pet, species="dog"))
            await self.repo.save(OrderPetModel(order_id=o.id, pet_id=p.id))
        return o

    async def issue(self, order, tipo="BOLETA", preview=False, **customer):
        return await IssueDocument(repo=self.repo, intifact=await self.intifact(), notifier=self.notifier).execute(
            order.id, tipo=tipo, customer=CustomerInput(**customer), actor_id=ADMIN, preview=preview)


async def _with_ctx(fn):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[m.__table__ for m in TABLES])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        return await fn(Ctx(PostgresInvoicingRepository(session=session), session, FakeIntifact()))
    finally:
        await session.close()
        await engine.dispose()


def run(fn):
    return asyncio.run(_with_ctx(fn))


def _status(exc_info) -> tuple[int, str]:
    detail = exc_info.value.detail
    return exc_info.value.status_code, detail.get("code") if isinstance(detail, dict) else detail


# ---------- Dominio ----------

def test_order_lines_spread_discount_and_match_the_total():
    items = [{"kind": "service_base", "name": "Baño", "qty": 1, "unit_price": 100},
             {"kind": "service_addon", "name": "Uñas", "qty": 1, "unit_price": 20},
             {"kind": "service_addon", "name": "Oídos", "qty": 1, "unit_price": 13.33}]
    lines = dom.order_lines(items, Decimal("120.00"), "Toby")
    assert [l["descripcion"] for l in lines] == ["Baño - Toby", "Uñas", "Oídos"]
    assert sum(Decimal(str(l["valorUnitario"])) * Decimal(str(l["cantidad"])) for l in lines) == Decimal("120.00")
    assert all(l["afectacion"] == "10" and l["unidad"] == "ZZ" for l in lines)

    same = dom.order_lines([{"kind": "service_addon", "name": "Lazo", "qty": 3, "unit_price": 5}], 15)
    assert (same[0]["cantidad"], same[0]["valorUnitario"]) == (3.0, 5.0)
    # 3 × 3.33 no da 10.00: la línea va como 1 unidad por el total
    odd = dom.order_lines([{"kind": "service_addon", "name": "Lazo", "qty": 3, "unit_price": 5}], 10)
    assert (odd[0]["cantidad"], odd[0]["valorUnitario"]) == (1.0, 10.0)
    assert dom.order_lines([], 0) == []
    assert dom.order_lines([], 50)[0]["valorUnitario"] == 50.0


@pytest.mark.parametrize("tipo,doc_type,number,field", [
    ("FACTURA", "1", "45678912", "customer_doc_type"),
    ("BOLETA", "1", "4567891", "customer_doc_number"),
    ("FACTURA", "6", "30123456789", "customer_doc_number"),
    ("BOLETA", "4", "12", "customer_doc_number"),
    ("BOLETA", "9", "45678912", "customer_doc_type"),
])
def test_check_customer_rejects(tipo, doc_type, number, field):
    with pytest.raises(dom.InvoicingInvalid) as exc:
        dom.check_customer(tipo, doc_type, number, "Ana")
    assert exc.value.field == field


def test_profile_customer_and_signature():
    assert dom.profile_customer("Ana", "Pérez", " 45678912 ") == ("1", "45678912", "Ana Pérez")
    assert dom.profile_customer("Ana", "Pérez", None) == ("1", "00000000", "Ana Pérez")
    assert dom.profile_customer("Ana", "Pérez", "X123") == ("1", "00000000", "Ana Pérez")
    sig = hmac.new(b"s3cr3t!!", b"1700.{\"a\":1}", hashlib.sha256).hexdigest()
    assert dom.valid_signature("s3cr3t!!", "1700", b'{"a":1}', sig.upper())
    assert not dom.valid_signature("otro-secreto", "1700", b'{"a":1}', sig)


# ---------- Configuración ----------

def test_config_encrypts_masks_and_tests_connection():
    async def scenario(ctx):
        empty = await GetIntifactIntegration(repo=ctx.repo).execute()
        assert (empty.status, empty.api_key_mask, empty.environment) == ("not_configured", None, None)

        with pytest.raises(HTTPException) as exc:
            await UpdateIntifactIntegration(repo=ctx.repo).execute(
                enabled=True, api_key="sk_live_x", company_ruc=RUC_EMISOR, webhook_secret=None, auto_issue=False,
                email_customer=True, actor_id=ADMIN)
        assert exc.value.detail["field"] == "api_key"
        with pytest.raises(HTTPException) as exc:
            await UpdateIntifactIntegration(repo=ctx.repo).execute(
                enabled=True, api_key=KEY, company_ruc=None, webhook_secret=None, auto_issue=False,
                email_customer=True, actor_id=ADMIN)
        assert exc.value.detail["field"] == "company_ruc"
        assert await ctx.repo.get("intifact") is None   # todo o nada

        view = await UpdateIntifactIntegration(repo=ctx.repo).execute(
            enabled=True, api_key=KEY, company_ruc=RUC_EMISOR, webhook_secret=SECRET, auto_issue=False,
            email_customer=True, actor_id=ADMIN)
        assert (view.status, view.api_key_mask, view.environment) == ("active", "fact_test_…1234", "test")
        stored = await ctx.repo.get("intifact")
        assert KEY not in stored.token_encrypted and crypto.decrypt_secret(stored.token_encrypted) == KEY
        assert crypto.decrypt_secret(stored.webhook_secret_encrypted) == SECRET

        # vacío conserva la key y el secreto
        view = await UpdateIntifactIntegration(repo=ctx.repo).execute(
            enabled=False, api_key="", company_ruc=RUC_EMISOR, webhook_secret=None, auto_issue=True,
            email_customer=False, actor_id=ADMIN)
        assert (view.status, view.api_key_mask, view.auto_issue) == ("disabled", "fact_test_…1234", True)

        result = await CheckIntifactConnection(repo=ctx.repo, client_factory=ctx.factory).execute()
        assert result.ok and "pruebas" in result.message
        ctx.fake.companies = [{"ruc": "20100000001"}]
        result = await CheckIntifactConnection(repo=ctx.repo, client_factory=ctx.factory).execute()
        assert not result.ok and "20100000001" in result.message
        assert (await GetIntifactIntegration(repo=ctx.repo).execute()).last_test_ok is False
        assert not any("send" in r for r in ctx.fake.requests)   # la prueba no emite
    run(scenario)


def test_disabled_integration_does_not_issue():
    async def scenario(ctx):
        with pytest.raises(HTTPException) as exc:
            await ctx.intifact()
        assert _status(exc) == (409, "INVOICING_NOT_CONFIGURED")
        await ctx.configure()
        await UpdateIntifactIntegration(repo=ctx.repo).execute(
            enabled=False, api_key=None, company_ruc=RUC_EMISOR, webhook_secret=None, auto_issue=False,
            email_customer=True, actor_id=ADMIN)
        with pytest.raises(HTTPException) as exc:
            await ctx.intifact()
        assert _status(exc) == (409, "INVOICING_NOT_CONFIGURED")
    run(scenario)


# ---------- Series ----------

def test_series_one_active_per_type_and_no_rename_when_used():
    async def scenario(ctx):
        await ctx.configure()
        with pytest.raises(HTTPException) as exc:
            await CreateSeries(repo=ctx.repo).execute(tipo="BOLETA", series="F002", first_number=1, is_active=True)
        assert exc.value.detail["code"] == "INVOICING_INVALID"
        with pytest.raises(HTTPException) as exc:
            await CreateSeries(repo=ctx.repo).execute(tipo="BOLETA", series="b001", first_number=1, is_active=True)
        assert _status(exc) == (409, "SERIES_EXISTS")

        b002 = await CreateSeries(repo=ctx.repo).execute(tipo="BOLETA", series="b002", first_number=500,
                                                         is_active=True)
        series = {s.series: s for s in await ListSeries(repo=ctx.repo).execute()}
        assert (series["B001"].is_active, series["B002"].is_active, series["F001"].is_active) == (False, True, True)
        assert series["B002"].next_number == 500

        o = await ctx.order(await ctx.user())
        doc = await ctx.issue(o)
        assert doc.number == "500"
        with pytest.raises(HTTPException) as exc:
            await UpdateSeries(repo=ctx.repo).execute(b002.id, series="B003", first_number=None, is_active=None)
        assert _status(exc) == (409, "SERIES_IN_USE")
        view = await UpdateSeries(repo=ctx.repo).execute(b002.id, series=None, first_number=None, is_active=None)
        assert (view.issued, view.last_number, view.next_number) == (1, 500, 501)
    run(scenario)


# ---------- Emisión ----------

def test_preview_sends_nothing_and_issue_creates_the_boleta():
    async def scenario(ctx):
        await ctx.configure()
        ctx.fake.next = 7
        user = await ctx.user()
        o = await ctx.order(user)

        view = await ctx.issue(o, preview=True)
        assert (view.number, view.customer_doc_number, view.customer_name, view.total) == (
            "B001-7", "45678912", "Ana Pérez", Decimal("120.00"))
        assert view.lines[0]["description"] == "Baño completo - Toby"
        assert ctx.fake.sent == [] and await ctx.repo.valid_document_for_order(o.id) is None

        doc = await ctx.issue(o)
        assert (doc.series, doc.number, doc.status, doc.total, doc.igv) == ("B001", "7", "ACEPTADO",
                                                                            Decimal("120.00"), Decimal("18.30"))
        body = ctx.fake.sent[0]
        assert (body["empresaRuc"], body["tipoDoc"], body["serie"], body["correlativo"]) == (RUC_EMISOR, "03", "B001", "7")
        assert (body["clienteTipoDoc"], body["clienteNumDoc"], body["tipoOperacion"]) == ("1", "45678912", "0101")
        assert "extraQueNoSeEnvia" not in body["detalle"][0]          # solo los campos que acepta /invoice/send
        assert body["formaPago"][0]["tipo"] == "Contado" and body["leyendas"][0]["legendCode"] == "1000"
        # correo al cliente, una sola vez
        assert len(ctx.emails) == 1 and ctx.emails[0]["to"] == user.email
        assert "/public/consultar/20615013898/03/B001/7/pdf" in ctx.emails[0]["html"]
        assert doc.customer_notified_at is not None

        with pytest.raises(HTTPException) as exc:
            await ctx.issue(o)
        assert _status(exc) == (409, "DOCUMENT_EXISTS")
    run(scenario)


def test_issue_guards():
    async def scenario(ctx):
        await ctx.configure()
        user = await ctx.user(dni=None)
        with pytest.raises(HTTPException) as exc:
            await ctx.issue(await ctx.order(user, paid=False))
        assert _status(exc) == (409, "ORDER_NOT_PAID")
        with pytest.raises(HTTPException) as exc:
            await ctx.issue(await ctx.order(user, status="cancelled"))
        assert _status(exc) == (409, "ORDER_CANCELLED")

        big = await ctx.order(user, total=700, items=[{"kind": "service_base", "name": "Spa", "qty": 1,
                                                        "unit_price": 700}])
        with pytest.raises(HTTPException) as exc:
            await ctx.issue(big)
        assert exc.value.status_code == 422 and exc.value.detail["field"] == "customer_doc_number"
        assert (await ctx.issue(big, doc_number="45678912", doc_type="1")).customer_doc_number == "45678912"

        small = await ctx.order(user)
        assert (await ctx.issue(small)).customer_doc_number == "00000000"   # consumidor final < S/ 700

        with pytest.raises(HTTPException) as exc:
            await ctx.issue(await ctx.order(user), tipo="FACTURA")
        assert exc.value.detail["field"] == "customer_doc_number"

        ctx.fake.compute_offset = Decimal("0.01")
        with pytest.raises(HTTPException) as exc:
            await ctx.issue(await ctx.order(user))
        assert _status(exc) == (409, "TOTAL_MISMATCH")
        assert len(ctx.fake.sent) == 2
    run(scenario)


def test_factura_registers_the_company_and_series_must_exist():
    async def scenario(ctx):
        await ctx.configure(factura=False)
        o = await ctx.order(await ctx.user())
        with pytest.raises(HTTPException) as exc:
            await ctx.issue(o, tipo="FACTURA", doc_number="20100070970", name="Empresa SAC")
        assert _status(exc) == (409, "SERIES_NOT_CONFIGURED")
        await CreateSeries(repo=ctx.repo).execute(tipo="FACTURA", series="F001", first_number=1, is_active=True)
        doc = await ctx.issue(o, tipo="FACTURA", doc_number="20100070970", name="Empresa SAC",
                              address="Av. Lima 123", email="pagos@empresa.pe")
        assert (doc.doc_type, doc.customer_doc_type, doc.series) == ("01", "6", "F001")
        assert ctx.fake.sent[0]["clienteDireccion"] == "Av. Lima 123"
        company = await ctx.repo.company_by_ruc("20100070970")
        assert (company.legal_name, company.email) == ("Empresa SAC", "pagos@empresa.pe")
        suggestions = await SearchCustomers(repo=ctx.repo).execute("2010007")
        assert suggestions[0].doc_number == "20100070970"
    run(scenario)


def test_pending_lists_paid_orders_and_rejected_ones_come_back():
    async def scenario(ctx):
        await ctx.configure()
        user = await ctx.user()
        o1 = await ctx.order(user)
        adj = await ctx.order(user, total=30, parent=o1.id, items=[
            {"kind": "price_adjustment", "name": "Ajuste por diferencia de peso", "qty": 1, "unit_price": 30}])
        await ctx.order(user, paid=False)
        await ctx.order(user, status="cancelled")

        page = await ListPending(repo=ctx.repo).execute()
        assert page.total == 2 and {r.kind for r in page.items} == {"service", "adjustment"}
        assert all(r.auto_issuable and r.suggested_doc_number == "45678912" for r in page.items)
        assert (await ListPending(repo=ctx.repo).execute(q="nadie")).total == 0
        assert (await ListPending(repo=ctx.repo).execute(q="Ana")).total == 2

        ctx.fake.default_status = "RECHAZADO"
        doc = await ctx.issue(adj)
        assert doc.status == "RECHAZADO" and ctx.emails == []
        page = await ListPending(repo=ctx.repo).execute()
        row = next(r for r in page.items if r.order_id == adj.id)
        assert row.failed_attempts == 1 and "RECHAZADO" in row.last_error
        assert doc.lines[0]["description"] == "Ajuste por diferencia de peso - Toby"
    run(scenario)


# ---------- Estado, anulación y archivos ----------

def test_refresh_void_and_order_returns_to_pending():
    async def scenario(ctx):
        await ctx.configure()
        o = await ctx.order(await ctx.user())
        ctx.fake.default_status = "ENCOLADO"
        doc = await ctx.issue(o)
        assert doc.status == "ENCOLADO" and ctx.emails == []

        intifact = await ctx.intifact()
        with pytest.raises(HTTPException) as exc:
            await VoidDocument(repo=ctx.repo, intifact=intifact).execute(doc.id, reason="error en el cliente")
        assert _status(exc) == (409, "NOT_VOIDABLE")

        ctx.fake.default_status = "ACEPTADO"
        await RefreshDocument(repo=ctx.repo, intifact=intifact, notifier=ctx.notifier).execute(doc.id)
        assert doc.status == "ACEPTADO" and len(ctx.emails) == 1

        await VoidDocument(repo=ctx.repo, intifact=intifact).execute(doc.id, reason="Datos del cliente errados")
        assert ctx.fake.cancels[0][0] == "/boleta/cancel" and "tipoDoc" not in ctx.fake.cancels[0][1]
        # SUNAT todavía dice ACEPTADO mientras se resuelve el resumen: queda ANULANDO y sigue vigente
        assert (doc.status, doc.void_reason) == ("ANULANDO", "Datos del cliente errados")
        assert (await ListPending(repo=ctx.repo).execute()).total == 0

        ctx.fake.status[doc.provider_id] = "ANULADO"
        assert await refresh_in_progress(ctx.repo, intifact, ctx.notifier) == 1
        assert doc.status == "ANULADO"
        assert (await ListPending(repo=ctx.repo).execute()).total == 1

        old = await ctx.issue(o)
        old.issue_date = date.today() - timedelta(days=10)
        await ctx.repo.save(old)
        with pytest.raises(HTTPException) as exc:
            await VoidDocument(repo=ctx.repo, intifact=intifact).execute(old.id, reason="tarde")
        assert _status(exc) == (409, "VOID_PERIOD_EXPIRED")
    run(scenario)


def test_factura_void_uses_comunicacion_de_baja():
    async def scenario(ctx):
        await ctx.configure()
        doc = await ctx.issue(await ctx.order(await ctx.user()), tipo="FACTURA", doc_number="20100070970",
                              name="Empresa SAC")
        await VoidDocument(repo=ctx.repo, intifact=await ctx.intifact()).execute(doc.id, reason="Error de RUC")
        path, body = ctx.fake.cancels[0]
        assert path == "/invoice/cancel" and body["tipoDoc"] == "01" and body["empresaRuc"] == RUC_EMISOR
    run(scenario)


# ---------- Webhook ----------

def _signed(body: dict, secret=SECRET, stamp=None):
    raw = json.dumps(body).encode()
    stamp = str(stamp if stamp is not None else int(datetime.now(timezone.utc).timestamp() * 1000))
    sig = hmac.new(secret.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()
    return dict(body=raw, event_header=body.get("event"), signature=sig, timestamp=stamp)


def test_webhook_updates_status_and_rejects_bad_signatures():
    async def scenario(ctx):
        await ctx.configure()
        ctx.fake.default_status = "ENCOLADO"
        doc = await ctx.issue(await ctx.order(await ctx.user()))
        hook = HandleWebhook(repo=ctx.repo, notifier=ctx.notifier)

        accepted = {"event": "document.accepted", "data": {"id": doc.provider_id, "codigoRespuesta": "0"}}
        assert (await hook.execute(**_signed(accepted)))["document"] == f"B001-{doc.number}"
        assert doc.status == "ACEPTADO" and len(ctx.emails) == 1

        by_number = {"event": "document.rejected", "data": {"serie": "B001", "correlativo": f"000{doc.number}",
                                                            "tipoDoc": "03", "descripcionRespuesta": "RUC inválido"}}
        await hook.execute(**_signed(by_number))
        assert (doc.status, doc.response_description) == ("RECHAZADO", "RUC inválido")

        other = {"event": "document.accepted", "data": {"id": "de-otra-app"}}
        assert (await hook.execute(**_signed(other)))["document"] is None
        assert (await hook.execute(**_signed({"event": "webhook.test"})))["ok"]

        for bad in (_signed(accepted, secret="otro-secreto-x"), _signed(accepted, stamp=1),
                    {**_signed(accepted), "signature": None}):
            with pytest.raises(HTTPException) as exc:
                await hook.execute(**bad)
            assert exc.value.status_code == 401
    run(scenario)


def test_webhook_without_secret_is_503():
    async def scenario(ctx):
        with pytest.raises(HTTPException) as exc:
            await HandleWebhook(repo=ctx.repo).execute(**_signed({"event": "webhook.test"}))
        assert exc.value.status_code == 503
    run(scenario)


# ---------- Emisión automática ----------

def test_auto_issue_only_when_enabled_and_without_admin_data():
    async def scenario(ctx):
        await ctx.configure(auto=False)
        with_dni = await ctx.order(await ctx.user())
        anonymous_big = await ctx.order(await ctx.user(dni=None), total=800, items=[
            {"kind": "service_base", "name": "Spa", "qty": 1, "unit_price": 800}])
        assert await auto_issue(ctx.repo, await ctx.intifact(), ctx.notifier) == (0, 0)

        await UpdateIntifactIntegration(repo=ctx.repo).execute(
            enabled=True, api_key=None, company_ruc=RUC_EMISOR, webhook_secret=None, auto_issue=True,
            email_customer=True, actor_id=ADMIN)
        assert await auto_issue(ctx.repo, await ctx.intifact(), ctx.notifier) == (1, 1)
        doc = await ctx.repo.valid_document_for_order(with_dni.id)
        assert doc.issued_by is None and doc.doc_type == "03"
        assert await ctx.repo.valid_document_for_order(anonymous_big.id) is None
    run(scenario)


# ---------- Momento de emisión y emisión de varias ----------

async def _set_trigger(ctx, trigger, auto=False):
    return await UpdateIntifactIntegration(repo=ctx.repo).execute(
        enabled=True, api_key=None, company_ruc=RUC_EMISOR, webhook_secret=None, auto_issue=auto,
        email_customer=True, actor_id=ADMIN, issue_trigger=trigger)


def test_issue_trigger_service_lists_and_issues_only_realized_services():
    async def scenario(ctx):
        await ctx.configure()
        assert (await GetIntifactIntegration(repo=ctx.repo).execute()).issue_trigger == "service"   # por defecto
        user = await ctx.user()
        done = await ctx.order(user)
        not_done = await ctx.order(user, status="created")
        adj_done = await ctx.order(user, total=30, parent=done.id, status="created", items=[
            {"kind": "price_adjustment", "name": "Ajuste por diferencia de peso", "qty": 1, "unit_price": 30}])
        adj_pending = await ctx.order(user, total=30, parent=not_done.id, status="created", items=[
            {"kind": "price_adjustment", "name": "Ajuste por diferencia de peso", "qty": 1, "unit_price": 30}])

        page = await ListPending(repo=ctx.repo).execute()
        assert page.issue_trigger == "service"
        assert {r.order_id for r in page.items} == {done.id, adj_done.id}
        with pytest.raises(HTTPException) as exc:
            await ctx.issue(not_done, preview=True)
        assert _status(exc) == (409, "ORDER_NOT_READY")
        with pytest.raises(HTTPException) as exc:
            await ctx.issue(adj_pending)
        assert _status(exc) == (409, "ORDER_NOT_READY")
        assert (await ctx.issue(adj_done)).status == "ACEPTADO"

        # Al confirmarse el pago: también las que aún no se realizan. Guardar sin trigger lo conserva.
        await _set_trigger(ctx, "payment")
        await _set_trigger(ctx, None)
        page = await ListPending(repo=ctx.repo).execute()
        assert page.issue_trigger == "payment"
        assert {r.order_id for r in page.items} == {done.id, not_done.id, adj_pending.id}
        assert (await ctx.issue(not_done)).status == "ACEPTADO"

        with pytest.raises(HTTPException) as exc:
            await _set_trigger(ctx, "never")
        assert exc.value.status_code == 422 and exc.value.detail["field"] == "issue_trigger"
    run(scenario)


def test_auto_issue_respects_the_issue_trigger():
    async def scenario(ctx):
        await ctx.configure()
        user = await ctx.user()
        realized = await ctx.order(user)
        upcoming = await ctx.order(user, status="created")
        await _set_trigger(ctx, "service", auto=True)
        assert await auto_issue(ctx.repo, await ctx.intifact(), ctx.notifier) == (1, 0)
        assert await ctx.repo.valid_document_for_order(realized.id) is not None
        assert await ctx.repo.valid_document_for_order(upcoming.id) is None

        await _set_trigger(ctx, "payment", auto=True)
        assert await auto_issue(ctx.repo, await ctx.intifact(), ctx.notifier) == (1, 0)
        assert await ctx.repo.valid_document_for_order(upcoming.id) is not None
    run(scenario)


def test_issue_batch_issues_the_ready_ones_and_reports_the_rest():
    async def scenario(ctx):
        await ctx.configure()
        a = await ctx.order(await ctx.user())
        b = await ctx.order(await ctx.user(dni=None), total=50, items=[
            {"kind": "service_base", "name": "Express", "qty": 1, "unit_price": 50}])   # consumidor final < 700
        big = await ctx.order(await ctx.user(dni=None), total=800, items=[
            {"kind": "service_base", "name": "Spa", "qty": 1, "unit_price": 800}])
        upcoming = await ctx.order(await ctx.user(), status="created")
        unknown = uuid4()

        batch = IssueBatch(repo=ctx.repo, intifact=await ctx.intifact(), notifier=ctx.notifier)
        results = await batch.execute([a.id, b.id, big.id, upcoming.id, unknown, a.id], actor_id=ADMIN)
        by_id = {r.order_id: r for r in results}
        assert len(results) == 5                                     # el repetido cuenta una vez
        assert by_id[a.id].ok and by_id[a.id].document.issued_by == ADMIN
        assert by_id[b.id].ok and by_id[b.id].document.customer_doc_number == "00000000"
        assert {by_id[a.id].document.number, by_id[b.id].document.number} == {"1", "2"}   # correlativos seguidos
        assert (by_id[big.id].ok, by_id[big.id].code) == (False, "NEEDS_CUSTOMER_DATA")
        assert (by_id[upcoming.id].ok, by_id[upcoming.id].code) == (False, "ORDER_NOT_READY")
        assert (by_id[unknown].ok, by_id[unknown].code) == (False, "NOT_FOUND")

        again = await batch.execute([a.id], actor_id=ADMIN)
        assert (again[0].ok, again[0].code) == (False, "DOCUMENT_EXISTS")
        for ids in ([], [uuid4() for _ in range(51)]):
            with pytest.raises(HTTPException) as exc:
                await batch.execute(ids, actor_id=ADMIN)
            assert exc.value.status_code == 422
    run(scenario)


# ---------- Registro, directorio, contabilidad y cliente ----------

def test_registry_directory_accounting_and_customer_access():
    async def scenario(ctx):
        await ctx.configure()
        ana = await ctx.user()
        b = await ctx.issue(await ctx.order(ana))
        f = await ctx.issue(await ctx.order(ana), tipo="FACTURA", doc_number="20100070970", name="Empresa | SAC")
        await SaveCompany(repo=ctx.repo).create(ruc="20512345678", legal_name="Otra SAC")
        with pytest.raises(HTTPException) as exc:
            await SaveCompany(repo=ctx.repo).create(ruc="20512345678", legal_name="Repetida")
        assert _status(exc) == (409, "COMPANY_EXISTS")

        page = await ListRegistry(repo=ctx.repo).execute(tipo=None, status=None, date_from=None, date_to=None,
                                                         q=None, environment="test", page=1, page_size=25)
        assert (page.total, page.accepted_amount) == (2, 240.0)
        assert page.items[0].pets == "Toby"
        page = await ListRegistry(repo=ctx.repo).execute(tipo="FACTURA", status=None, date_from=None, date_to=None,
                                                         q="B001", environment=None, page=1, page_size=25)
        assert page.total == 0

        directory = await ListDirectory(repo=ctx.repo).execute(q=None, origin=None, with_documents=True, page=1,
                                                               page_size=25)
        by_doc = {r.doc_number: r for r in directory.items}
        assert by_doc["45678912"].history.boletas == 1 and by_doc["20100070970"].history.facturas == 1
        assert "20512345678" not in by_doc

        month = b.issue_date.strftime("%Y-%m")
        months = await accounting.months(ctx.repo, "test")
        assert (months[0].month, months[0].boletas, months[0].facturas, months[0].total) == (
            month, 1, 1, Decimal("240.00"))
        content, name = await accounting.sales_register(ctx.repo, month, "test", RUC_EMISOR)
        lines = content.decode().strip().split("\r\n")
        assert name.startswith(f"LE{RUC_EMISOR}") and name.endswith("11.txt") and len(lines) == 2
        fields = next(l for l in lines if l.split("|")[5] == "01").split("|")
        assert len(fields) == 37 and fields[5] == "01" and fields[11] == "Empresa   SAC"   # sin «|»
        assert fields[24] == "120.00" and fields[34] == "1"
        assert (await accounting.summary_totals(ctx.repo, month, "test", RUC_EMISOR))[:2] == b"PK"
        assert (await accounting.summary_invoices(ctx.repo, month, "test", RUC_EMISOR))[:2] == b"PK"
        archive = zipfile.ZipFile(io.BytesIO(await accounting.compendium(ctx.repo, await ctx.intifact(), month,
                                                                         "boletas")))
        assert archive.namelist() == [f"B001-{b.number.zfill(8)}.pdf"]
        with pytest.raises(HTTPException):
            accounting.month_range("2026-13")

        docs = await CustomerDocuments(repo=ctx.repo).execute(order_id=b.order_id, user_id=ana.id)
        assert [d.id for d in docs] == [b.id]
        assert (await own_document(ctx.repo, f.id, ana.id)).id == f.id
        with pytest.raises(HTTPException):
            await CustomerDocuments(repo=ctx.repo).execute(order_id=b.order_id, user_id=uuid4())
        with pytest.raises(HTTPException):
            await own_document(ctx.repo, b.id, uuid4())
    run(scenario)


def test_apply_status_keeps_voiding_until_resolved():
    async def scenario(ctx):
        await ctx.configure()
        doc = await ctx.issue(await ctx.order(await ctx.user()))
        doc.status = "ANULANDO"
        await apply_status(ctx.repo, doc, {"sunat": {"estado": "ACEPTADO"}})
        assert doc.status == "ANULANDO"
        await apply_status(ctx.repo, doc, {"estado": "ANULADO"})
        assert doc.status == "ANULADO"
    run(scenario)
