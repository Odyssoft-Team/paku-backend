"""Facturación electrónica con Intifact (feature 0023).

Admin (`/admin`): integración, series, pendientes de emitir, vista previa y emisión, registro, detalle, archivos,
anulación, directorio de clientes y reportes contables. Público: webhook de Intifact y comprobantes del cliente.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import get_async_session
from app.modules.invoicing.api.schemas import (
    AccountingMonthOut,
    CompanyIn,
    CompanyOut,
    CompanyUpdateIn,
    ConnectionTestOut,
    CustomerDocumentOut,
    DirectoryPageOut,
    DirectoryRowOut,
    DocumentDetailOut,
    DocumentOut,
    IntifactIntegrationIn,
    IntifactIntegrationOut,
    IssueBatchIn,
    IssueBatchItemOut,
    IssueBatchOut,
    IssueIn,
    PendingOut,
    PendingPageOut,
    PreviewOut,
    ReadinessOut,
    RegistryOut,
    SeriesCreateIn,
    SeriesOut,
    SeriesUpdateIn,
    SuggestionOut,
    VoidIn,
)
from app.modules.invoicing.app import accounting
from app.modules.invoicing.app.config import (
    CheckIntifactConnection,
    GetIntifactIntegration,
    IntifactIntegration,
    UpdateIntifactIntegration,
    active_intifact,
    current_environment,
    invoicing_readiness,
)
from app.modules.invoicing.app.directory import ListDirectory, SaveCompany, SearchCustomers
from app.modules.invoicing.app.documents import (
    CustomerDocuments,
    CustomerInput,
    DocumentFile,
    DocumentRow,
    GetDocument,
    IssueDocument,
    IssueBatch,
    ListPending,
    ListRegistry,
    Preview,
    RefreshDocument,
    VoidDocument,
    days_left_to_void,
    document_file,
    number_of,
    own_document,
    rows_for,
    type_name,
)
from app.modules.invoicing.app.jobs import HandleWebhook
from app.modules.invoicing.app.series import CreateSeries, ListSeries, UpdateSeries
from app.modules.invoicing.domain.intifact import ACEPTADO, ANULADO, ANULANDO
from app.modules.invoicing.infra.postgres_invoicing_repository import PostgresInvoicingRepository
from app.modules.messaging.app.sender import send_email

admin_router = APIRouter(tags=["invoicing-admin"])
router = APIRouter(prefix="/invoicing", tags=["invoicing"])

admin_only = require_roles("admin")


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresInvoicingRepository:
    return PostgresInvoicingRepository(session=session)


def get_notifier(session: AsyncSession = Depends(get_async_session)):
    async def notify(**kw: Any) -> Any:
        return await send_email(session, **kw)
    return notify


async def get_intifact(repo: PostgresInvoicingRepository = Depends(get_repo)):
    return await active_intifact(repo)


def _document_out(row: DocumentRow) -> dict:
    d = row.doc
    return dict(
        id=d.id, order_id=d.order_id, order_kind=row.order_kind, pets=row.pets, type=type_name(d),
        doc_type=d.doc_type, series=d.series, number=d.number, full_number=number_of(d), issue_date=d.issue_date,
        customer_doc_type=d.customer_doc_type, customer_doc_number=d.customer_doc_number,
        customer_name=d.customer_name, customer_address=d.customer_address, customer_email=d.customer_email,
        taxable_amount=d.taxable_amount, igv=d.igv, total=d.total, currency=d.currency, status=d.status,
        response_code=d.response_code, response_description=d.response_description, environment=d.environment,
        automatic=d.issued_by is None, customer_notified_at=d.customer_notified_at,
        days_left_to_void=days_left_to_void(d) if d.status == ACEPTADO else 0, created_at=d.created_at)


def _detail_out(row: DocumentRow) -> DocumentDetailOut:
    d = row.doc
    return DocumentDetailOut(**_document_out(row), lines=d.lines or [], amount_in_words=d.amount_in_words,
                             hash=d.hash, void_reason=d.void_reason, voided_on=d.voided_on)


def _attachment(content: bytes, media_type: str, filename: str, inline: bool = False) -> Response:
    disposition = "inline" if inline else "attachment"
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'{disposition}; filename="{filename}"'})


# ---------- Integración ----------

async def _integration_out(view: IntifactIntegration, session, repo) -> IntifactIntegrationOut:
    readiness = await invoicing_readiness(session, repo)
    return IntifactIntegrationOut(**asdict(view), readiness=ReadinessOut(**asdict(readiness)))


@admin_router.get("/integrations/intifact", response_model=IntifactIntegrationOut)
async def get_intifact_integration(
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    session: AsyncSession = Depends(get_async_session),
) -> IntifactIntegrationOut:
    """Configuración de Intifact (secretos enmascarados) y lo que falta para emitir (`readiness`)."""
    return await _integration_out(await GetIntifactIntegration(repo=repo).execute(), session, repo)


@admin_router.put("/integrations/intifact", response_model=IntifactIntegrationOut)
async def update_intifact_integration(
    payload: IntifactIntegrationIn,
    current: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    session: AsyncSession = Depends(get_async_session),
) -> IntifactIntegrationOut:
    """
    Guarda API key y secreto del webhook (cifrados; vacíos conservan los guardados), RUC emisor, activo, momento de
    emisión (`issue_trigger`; ausente lo conserva), emisión automática y aviso por correo. 422 `INVOICING_INVALID` con `field` (no guarda nada); 503
    `ENCRYPTION_UNAVAILABLE` sin llave en el servidor.
    """
    view = await UpdateIntifactIntegration(repo=repo).execute(
        enabled=payload.enabled, api_key=payload.api_key, company_ruc=payload.company_ruc,
        webhook_secret=payload.webhook_secret, auto_issue=payload.auto_issue, email_customer=payload.email_customer,
        actor_id=current.id, issue_trigger=payload.issue_trigger)
    return await _integration_out(view, session, repo)


@admin_router.post("/integrations/intifact/test", response_model=ConnectionTestOut)
async def test_intifact_connection(
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
) -> ConnectionTestOut:
    """Lista las empresas de la cuenta (**no emite nada**) y verifica que el RUC emisor esté. Queda como última
    prueba. 409 `INVOICING_NOT_CONFIGURED` sin key o RUC."""
    return ConnectionTestOut(**asdict(await CheckIntifactConnection(repo=repo).execute()))


# ---------- Series ----------

@admin_router.get("/invoicing/series", response_model=list[SeriesOut])
async def list_series(_: CurrentUser = Depends(admin_only),
                      repo: PostgresInvoicingRepository = Depends(get_repo)) -> list[SeriesOut]:
    return [SeriesOut(**asdict(s)) for s in await ListSeries(repo=repo).execute()]


@admin_router.post("/invoicing/series", response_model=SeriesOut, status_code=status.HTTP_201_CREATED)
async def create_series(payload: SeriesCreateIn, _: CurrentUser = Depends(admin_only),
                        repo: PostgresInvoicingRepository = Depends(get_repo)) -> SeriesOut:
    """Activarla desactiva la otra del mismo tipo. 409 `SERIES_EXISTS`; 422 `INVOICING_INVALID` (formato)."""
    return SeriesOut(**asdict(await CreateSeries(repo=repo).execute(
        tipo=payload.type, series=payload.series, first_number=payload.first_number, is_active=payload.is_active)))


@admin_router.patch("/invoicing/series/{series_id}", response_model=SeriesOut)
async def update_series(series_id: UUID, payload: SeriesUpdateIn, _: CurrentUser = Depends(admin_only),
                        repo: PostgresInvoicingRepository = Depends(get_repo)) -> SeriesOut:
    """Una serie con comprobantes no se renombra (409 `SERIES_IN_USE`)."""
    return SeriesOut(**asdict(await UpdateSeries(repo=repo).execute(
        series_id, series=payload.series, first_number=payload.first_number, is_active=payload.is_active)))


# ---------- Pendientes y emisión ----------

@admin_router.get("/invoicing/pending", response_model=PendingPageOut)
async def list_pending(
    date_from: Optional[date] = Query(None, description="Fecha de compra (Lima), desde."),
    date_to: Optional[date] = None,
    q: Optional[str] = Query(None, description="Nombre, DNI o correo del cliente."),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
) -> PendingPageOut:
    """Órdenes pagadas (servicio o ajuste por peso), no canceladas, sin comprobante vigente y listas según el momento
    de emisión: con `service`, solo los servicios realizados (y los ajustes de un servicio realizado)."""
    result = await ListPending(repo=repo).execute(date_from=date_from, date_to=date_to, q=q, page=page,
                                                  page_size=page_size)
    return PendingPageOut(items=[PendingOut(**asdict(r)) for r in result.items], total=result.total,
                          total_amount=result.total_amount, issue_trigger=result.issue_trigger)


def _customer_input(payload: IssueIn) -> CustomerInput:
    return CustomerInput(doc_type=payload.customer_doc_type, doc_number=payload.customer_doc_number,
                         name=payload.customer_name, address=payload.customer_address, email=payload.customer_email)


@admin_router.post("/invoicing/orders/{order_id}/preview", response_model=PreviewOut)
async def preview_document(
    order_id: UUID,
    payload: IssueIn,
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    intifact=Depends(get_intifact),
) -> PreviewOut:
    """Lo que se emitiría (número, líneas, IGV y total) calculado por Intifact, **sin enviar nada a SUNAT**."""
    view: Preview = await IssueDocument(repo=repo, intifact=intifact).execute(
        order_id, tipo=payload.type, customer=_customer_input(payload), actor_id=None, preview=True)
    return PreviewOut(**asdict(view))


@admin_router.post("/invoicing/orders/{order_id}/issue", response_model=DocumentDetailOut,
                   status_code=status.HTTP_201_CREATED)
async def issue_document(
    order_id: UUID,
    payload: IssueIn,
    current: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    intifact=Depends(get_intifact),
    notifier=Depends(get_notifier),
) -> DocumentDetailOut:
    """
    Emite la boleta o factura de una orden pagada. 404 orden; 409 `ORDER_NOT_PAID`, `ORDER_CANCELLED`,
    `ORDER_NOT_READY` (con el momento `service`, el servicio aún no se realiza), `DOCUMENT_EXISTS`, `SERIES_NOT_CONFIGURED`, `TOTAL_MISMATCH`, `INVOICING_NOT_CONFIGURED`; 422 `INVOICING_INVALID`
    (datos del cliente, o boleta de S/ 700 o más sin documento) o `INTIFACT_ERROR`; 502 si Intifact no responde.
    """
    doc = await IssueDocument(repo=repo, intifact=intifact, notifier=notifier).execute(
        order_id, tipo=payload.type, customer=_customer_input(payload), actor_id=current.id)
    return _detail_out((await rows_for(repo, [doc]))[0])


@admin_router.post("/invoicing/issue-batch", response_model=IssueBatchOut)
async def issue_batch(
    payload: IssueBatchIn,
    current: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    intifact=Depends(get_intifact),
    notifier=Depends(get_notifier),
) -> IssueBatchOut:
    """
    Emite boletas de varias órdenes listas (hasta 50) con los datos del perfil, como la emisión automática. Las que
    necesitan datos del admin vuelven con `NEEDS_CUSTOMER_DATA` y se emiten de a una. Responde 200 con el resultado de
    cada orden: un error no detiene las demás.
    """
    results = await IssueBatch(repo=repo, intifact=intifact, notifier=notifier).execute(
        payload.order_ids, actor_id=current.id)
    docs = {r.document.id: r for r in await rows_for(repo, [i.document for i in results if i.document is not None])}
    items = [IssueBatchItemOut(order_id=i.order_id, ok=i.ok, code=i.code, message=i.message,
                               document=DocumentOut(**_document_out(docs[i.document.id])) if i.document else None)
             for i in results]
    return IssueBatchOut(items=items, issued=sum(1 for i in results if i.ok), failed=sum(1 for i in results if not i.ok))


@admin_router.get("/invoicing/orders/{order_id}/documents", response_model=list[DocumentOut])
async def order_documents(order_id: UUID, _: CurrentUser = Depends(admin_only),
                          repo: PostgresInvoicingRepository = Depends(get_repo)) -> list[DocumentOut]:
    """Todos los comprobantes de la orden, incluidos los rechazados (para el detalle de la orden)."""
    return [DocumentOut(**_document_out(r)) for r in await rows_for(repo, await repo.documents_for_order(order_id))]


# ---------- Registro ----------

@admin_router.get("/invoicing/documents", response_model=RegistryOut)
async def list_documents(
    type: Optional[Literal["BOLETA", "FACTURA"]] = None,
    status_: Optional[str] = Query(None, alias="status",
                                   description="Uno de SUNAT, o PENDIENTE (en curso) o FALLIDO (rechazado/error)."),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    q: Optional[str] = Query(None, description="Cliente, documento o número (B001-12)."),
    environment: Optional[Literal["test", "live"]] = Query(None, description="Sin valor: ambos."),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
) -> RegistryOut:
    result = await ListRegistry(repo=repo).execute(tipo=type, status=status_, date_from=date_from, date_to=date_to,
                                                   q=q, environment=environment, page=page, page_size=page_size)
    return RegistryOut(items=[DocumentOut(**_document_out(r)) for r in result.items], total=result.total,
                       accepted_amount=result.accepted_amount)


@admin_router.get("/invoicing/documents/{document_id}", response_model=DocumentDetailOut)
async def get_document(document_id: UUID, _: CurrentUser = Depends(admin_only),
                       repo: PostgresInvoicingRepository = Depends(get_repo)) -> DocumentDetailOut:
    """El comprobante tal como se emitió (cabecera, cliente, líneas y totales) para verlo como documento."""
    return _detail_out(await GetDocument(repo=repo).execute(document_id))


@admin_router.post("/invoicing/documents/{document_id}/refresh", response_model=DocumentDetailOut)
async def refresh_document(
    document_id: UUID,
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    intifact=Depends(get_intifact),
    notifier=Depends(get_notifier),
) -> DocumentDetailOut:
    """Consulta a Intifact el estado SUNAT del comprobante."""
    await RefreshDocument(repo=repo, intifact=intifact, notifier=notifier).execute(document_id)
    return _detail_out(await GetDocument(repo=repo).execute(document_id))


@admin_router.post("/invoicing/documents/{document_id}/void", response_model=DocumentDetailOut)
async def void_document(
    document_id: UUID,
    payload: VoidIn,
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    intifact=Depends(get_intifact),
) -> DocumentDetailOut:
    """Anula ante SUNAT: comunicación de baja (factura) o resumen diario (boleta). Solo aceptados y hasta 7 días
    (409 `NOT_VOIDABLE`, `VOID_PERIOD_EXPIRED`). Queda ANULANDO hasta que SUNAT responde; la orden vuelve a
    «por emitir» al quedar ANULADO."""
    await VoidDocument(repo=repo, intifact=intifact).execute(document_id, reason=payload.reason)
    return _detail_out(await GetDocument(repo=repo).execute(document_id))


@admin_router.get("/invoicing/documents/{document_id}/{kind}", response_class=Response)
async def download_document_file(
    document_id: UUID,
    kind: Literal["pdf", "xml", "cdr"],
    format: Literal["a4", "ticket80", "ticket58"] = Query("a4", description="Solo PDF."),
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
    intifact=Depends(get_intifact),
) -> Response:
    """PDF, XML firmado o CDR (constancia de SUNAT; 409 `CDR_NOT_READY` mientras no responde)."""
    content, media_type, filename = await DocumentFile(repo=repo, intifact=intifact).execute(document_id, kind, format)
    return _attachment(content, media_type, filename, inline=kind == "pdf")


# ---------- Directorio de clientes ----------

@admin_router.get("/invoicing/customers", response_model=DirectoryPageOut)
async def list_customers(
    q: Optional[str] = None,
    origin: Optional[Literal["USER", "COMPANY"]] = None,
    with_documents: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
) -> DirectoryPageOut:
    """Clientes de facturación: usuarios con documento y empresas con RUC, con su historial de comprobantes."""
    result = await ListDirectory(repo=repo).execute(q=q, origin=origin, with_documents=with_documents, page=page,
                                                    page_size=page_size)
    return DirectoryPageOut(items=[DirectoryRowOut(**asdict(r)) for r in result.items], total=result.total)


@admin_router.get("/invoicing/customers/search", response_model=list[SuggestionOut])
async def search_customers(q: str = "", _: CurrentUser = Depends(admin_only),
                           repo: PostgresInvoicingRepository = Depends(get_repo)) -> list[SuggestionOut]:
    """Autocompletar al emitir (mínimo 2 caracteres): número de documento primero."""
    return [SuggestionOut(**asdict(s)) for s in await SearchCustomers(repo=repo).execute(q)]


def _company_out(c) -> CompanyOut:
    return CompanyOut(id=c.id, ruc=c.ruc, legal_name=c.legal_name, trade_name=c.trade_name, address=c.address,
                      email=c.email, phone=c.phone, notes=c.notes)


@admin_router.post("/invoicing/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(payload: CompanyIn, _: CurrentUser = Depends(admin_only),
                         repo: PostgresInvoicingRepository = Depends(get_repo)) -> CompanyOut:
    """409 `COMPANY_EXISTS` si el RUC ya está."""
    return _company_out(await SaveCompany(repo=repo).create(**payload.model_dump()))


@admin_router.patch("/invoicing/companies/{company_id}", response_model=CompanyOut)
async def update_company(company_id: UUID, payload: CompanyUpdateIn, _: CurrentUser = Depends(admin_only),
                         repo: PostgresInvoicingRepository = Depends(get_repo)) -> CompanyOut:
    return _company_out(await SaveCompany(repo=repo).update(company_id, **payload.model_dump(exclude_unset=True)))


# ---------- Reportes contables ----------

@admin_router.get("/invoicing/accounting", response_model=list[AccountingMonthOut])
async def accounting_months(_: CurrentUser = Depends(admin_only),
                            repo: PostgresInvoicingRepository = Depends(get_repo)) -> list[AccountingMonthOut]:
    """Meses con comprobantes en el ambiente actual, con cantidades y total."""
    return [AccountingMonthOut(**asdict(m)) for m in await accounting.months(repo, await current_environment(repo))]


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@admin_router.get("/invoicing/accounting/{month}/{report}", response_class=Response)
async def accounting_report(
    month: str,
    report: Literal["resumen-totales", "resumen-facturas", "compendio-boletas", "compendio-facturas",
                    "registro-ventas"],
    _: CurrentUser = Depends(admin_only),
    repo: PostgresInvoicingRepository = Depends(get_repo),
) -> Response:
    """Resumen de totales y de facturas (xlsx), compendio de PDF (zip) o registro de ventas PLE 14.1 (txt)."""
    accounting.month_range(month)
    if report.startswith("compendio"):
        kind = "boletas" if report == "compendio-boletas" else "facturas"
        content = await accounting.compendium(repo, await active_intifact(repo), month, kind)
        return _attachment(content, "application/zip", f"compendio-{kind}-{month}.zip")
    environment = await current_environment(repo)
    model = await repo.get("intifact")
    ruc = (model.company_ruc if model else None) or ""
    if report == "resumen-totales":
        return _attachment(await accounting.summary_totals(repo, month, environment, ruc), XLSX,
                           f"resumen-totales-{month}.xlsx")
    if report == "resumen-facturas":
        return _attachment(await accounting.summary_invoices(repo, month, environment, ruc), XLSX,
                           f"resumen-facturas-{month}.xlsx")
    content, filename = await accounting.sales_register(repo, month, environment, ruc)
    return _attachment(content, "text/plain; charset=utf-8", filename)


# ---------- Público: webhook y app del cliente ----------

@router.post("/webhook", include_in_schema=False)
async def intifact_webhook(
    request: Request,
    repo: PostgresInvoicingRepository = Depends(get_repo),
    notifier=Depends(get_notifier),
    x_facturacion_event: Optional[str] = Header(None),
    x_facturacion_signature: Optional[str] = Header(None),
    x_facturacion_timestamp: Optional[str] = Header(None),
) -> dict:
    """Avisos de Intifact (document.accepted, document.rejected, document.queue_failed, document.retried,
    ticket.resolved, webhook.test). Registrar en el portal de Intifact: `https://<api>/invoicing/webhook`."""
    return await HandleWebhook(repo=repo, notifier=notifier).execute(
        body=await request.body(), event_header=x_facturacion_event, signature=x_facturacion_signature,
        timestamp=x_facturacion_timestamp)


@router.get("/orders/{order_id}/documents", response_model=list[CustomerDocumentOut])
async def my_order_documents(
    order_id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresInvoicingRepository = Depends(get_repo),
) -> list[CustomerDocumentOut]:
    """Comprobantes de una orden propia (boleta o factura). 404 si la orden no es del usuario."""
    docs = await CustomerDocuments(repo=repo).execute(order_id=order_id, user_id=current.id)
    return [CustomerDocumentOut(id=d.id, type=type_name(d), full_number=number_of(d), issue_date=d.issue_date,
                                total=d.total, status=d.status,
                                pdf_available=d.status in (ACEPTADO, ANULANDO, ANULADO)) for d in docs]


@router.get("/documents/{document_id}/pdf", response_class=Response)
async def my_document_pdf(
    document_id: UUID,
    format: Literal["a4", "ticket80", "ticket58"] = "a4",
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresInvoicingRepository = Depends(get_repo),
) -> Response:
    """PDF de un comprobante propio aceptado por SUNAT."""
    doc = await own_document(repo, document_id, current.id)
    content, media_type, filename = await document_file(await active_intifact(repo, require_enabled=False), doc,
                                                        "pdf", format)
    return _attachment(content, media_type, filename, inline=True)
