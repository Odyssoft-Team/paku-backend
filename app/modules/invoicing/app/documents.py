"""Comprobantes electrónicos de las órdenes pagadas (feature 0023): pendientes, vista previa, emisión, estado SUNAT,
anulación, archivos, registro y aviso al cliente.

Reglas (spec 0023):
- Cada orden pagada (servicio o ajuste por peso) lleva su comprobante; uno vigente a la vez.
- Una orden está lista para emitir según el momento configurado: al realizarse el servicio o al confirmarse el pago.
- Los precios incluyen IGV. El total del comprobante es exactamente lo cobrado; si Intifact calcula otro, no se emite.
- Boleta a consumidor final solo por debajo de S/ 700. Factura solo con RUC.
- Anulación solo de aceptados y hasta 7 días después de emitidos.
"""
from __future__ import annotations

import asyncio
import html
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from fastapi import HTTPException

from app.core.timezone import LIMA_TZ, today_lima
from app.modules.invoicing.app.config import ActiveIntifact, current_issue_trigger, invalid
from app.modules.invoicing.app.series import active_series, local_next_number
from app.modules.invoicing.domain.intifact import (
    ACEPTADO,
    ANULADO,
    ANULANDO,
    BOLETA,
    DIAS_PARA_ANULAR,
    DNI,
    ENCOLADO,
    FACTURA,
    LIMITE_BOLETA_ANONIMA,
    MAX_BATCH_ISSUE,
    TRIGGER_SERVICE,
    NOMBRE_TIPO,
    RUC,
    TIPO_DOC,
    InvoicingInvalid,
    build_send_body,
    check_customer,
    is_anonymous,
    money,
    order_lines,
    preview_lines,
    profile_customer,
    public_pdf_url,
    ready_to_issue,
)
from app.modules.invoicing.infra.intifact_client import IntifactError
from app.modules.invoicing.infra.models import InvoiceDocumentModel, InvoicingCompanyModel, utcnow

logger = logging.getLogger(__name__)

# Una emisión a la vez por proceso: dos emisiones simultáneas pedirían el mismo correlativo.
_issue_lock = asyncio.Lock()

Notifier = Callable[..., Awaitable[Any]]


def intifact_http_error(exc: IntifactError) -> HTTPException:
    code = 502 if exc.status_code >= 500 else 409 if exc.status_code == 409 else 422
    return HTTPException(status_code=code, detail={"code": "INTIFACT_ERROR",
                                                   "message": f"Facturación electrónica: {exc.detail()}"})


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": code, "message": message})


def _not_found(message: str = "Comprobante no encontrado.") -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": message})


def number_of(doc: InvoiceDocumentModel) -> str:
    return f"{doc.series}-{doc.number}"


def days_left_to_void(doc: InvoiceDocumentModel, today: Optional[date] = None) -> int:
    return max(0, DIAS_PARA_ANULAR - ((today or today_lima()) - doc.issue_date).days)


def _lima_day(when: Optional[datetime]) -> Optional[date]:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(LIMA_TZ).date()


def _full_name(user) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip() if user else ""


def order_kind(order) -> str:
    return "adjustment" if order.parent_order_id else "service"


# ---------- Emisión ----------

@dataclass(frozen=True)
class CustomerInput:
    """Datos del cliente que envía el admin. Vacíos: se toman del perfil (boleta)."""
    doc_type: Optional[str] = None
    doc_number: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None


@dataclass(frozen=True)
class Preview:
    type: str
    number: str                      # el que tendría si se emite ahora
    issue_date: date
    customer_doc_type: str
    customer_doc_number: str
    customer_name: str
    customer_address: Optional[str]
    customer_email: Optional[str]
    lines: list[dict]
    taxable_amount: Decimal
    igv: Decimal
    total: Decimal
    amount_in_words: Optional[str]
    environment: str


def _customer(tipo: str, data: CustomerInput, user) -> tuple[tuple[str, str, str], Optional[str], Optional[str]]:
    if data.doc_number and data.doc_number.strip():
        doc_type = data.doc_type or (RUC if tipo == FACTURA else DNI)
        customer = check_customer(tipo, doc_type, data.doc_number, data.name or _full_name(user))
    elif tipo == FACTURA:
        raise InvoicingInvalid("customer_doc_number", "La factura necesita el RUC del cliente.")
    else:
        doc_type, number, name = profile_customer(user.first_name if user else "", user.last_name if user else "",
                                                  user.dni if user else None)
        customer = check_customer(tipo, doc_type, number, data.name or name)
    address = (data.address or "").strip() or None
    email = (data.email or "").strip() or (user.email if user else None)
    return customer, address, email


async def _order_for_invoice(repo, order_id: UUID, trigger: str):
    order = await repo.get_order(order_id)
    if order is None:
        raise _not_found("Orden no encontrada.")
    if order.payment_status != "paid":
        raise _conflict("ORDER_NOT_PAID", "Solo se emite el comprobante de una orden pagada.")
    if order.status == "cancelled":
        raise _conflict("ORDER_CANCELLED", "La orden está cancelada: no lleva comprobante.")
    parent = await repo.get_order(order.parent_order_id) if order.parent_order_id else None
    if not ready_to_issue(trigger, order_status=order.status, parent_status=parent.status if parent else None,
                          is_adjustment=order.parent_order_id is not None):
        raise _conflict("ORDER_NOT_READY", "El comprobante se emite al realizarse el servicio y este aún no se realiza "
                                           "(Configuración → Intifact → Momento de emisión).")
    if await repo.valid_document_for_order(order.id):
        raise _conflict("DOCUMENT_EXISTS", "Esta orden ya tiene un comprobante electrónico vigente.")
    return order


@dataclass
class IssueDocument:
    """Vista previa (`preview=True`, no envía ni guarda nada) o emisión del comprobante de una orden pagada."""
    repo: Any
    intifact: ActiveIntifact
    notifier: Optional[Notifier] = None

    async def execute(self, order_id: UUID, *, tipo: str, customer: CustomerInput, actor_id: Optional[UUID],
                      preview: bool = False):
        if tipo not in TIPO_DOC:
            raise invalid(InvoicingInvalid("type", "El tipo es BOLETA o FACTURA."))
        async with _issue_lock:
            return await self._run(order_id, tipo=tipo, data=customer, actor_id=actor_id, preview=preview)

    async def _run(self, order_id: UUID, *, tipo: str, data: CustomerInput, actor_id: Optional[UUID], preview: bool):
        repo, client = self.repo, self.intifact.client
        order = await _order_for_invoice(repo, order_id, self.intifact.issue_trigger)
        user = (await repo.users_by_id([order.user_id])).get(order.user_id)
        pets = await repo.order_pet_names([order.id])
        try:
            customer, address, email = _customer(tipo, data, user)
        except InvoicingInvalid as exc:
            raise invalid(exc) from exc
        total = money(order.total_snapshot)
        if tipo == BOLETA and is_anonymous(customer[0], customer[1]) and total >= LIMITE_BOLETA_ANONIMA:
            raise invalid(InvoicingInvalid(
                "customer_doc_number",
                "Desde S/ 700 la boleta necesita el documento del cliente (no se emite a consumidor final)."))
        items = order_lines(order.items_snapshot, total, pets.get(order.id))
        if not items:
            raise _conflict("NOTHING_TO_INVOICE", "La orden no tiene montos que facturar.")
        doc_type = TIPO_DOC[tipo]
        series = await active_series(repo, tipo)
        today = today_lima()
        try:
            calculo = await client.compute(items, prices_include_igv=True)
            computed = money(calculo.get("montoImpVenta"))
            if computed != total:
                raise _conflict("TOTAL_MISMATCH", f"Intifact calcula S/ {computed} y la orden cobró S/ {total}: "
                                                  "no se emite. Revisa las líneas de la orden.")
            number = str(max(await client.next_number(self.intifact.ruc, doc_type, series.series),
                             await local_next_number(repo, series, self.intifact.environment)))
            view = Preview(
                type=tipo, number=f"{series.series}-{number}", issue_date=today, customer_doc_type=customer[0],
                customer_doc_number=customer[1], customer_name=customer[2], customer_address=address,
                customer_email=email, lines=preview_lines(items, calculo), taxable_amount=money(calculo.get("valorVenta")),
                igv=money(calculo.get("montoIgv")), total=computed, amount_in_words=calculo.get("montoEnLetras"),
                environment=self.intifact.environment)
            if preview:
                return view
            sent = await client.send(build_send_body(
                calculo=calculo, ruc=self.intifact.ruc, tipo_doc=doc_type, serie=series.series, correlativo=number,
                fecha=today.isoformat(), customer=customer, address=address))
        except IntifactError as exc:
            raise intifact_http_error(exc) from exc

        doc = InvoiceDocumentModel(
            order_id=order.id, user_id=order.user_id, doc_type=doc_type, series=series.series, number=number,
            issue_date=today, customer_doc_type=customer[0], customer_doc_number=customer[1],
            customer_name=customer[2], customer_address=address, customer_email=email,
            taxable_amount=view.taxable_amount, igv=view.igv, total=view.total, currency="PEN",
            provider_id=str(sent.get("id")) if sent.get("id") else None, status=sent.get("estado") or ENCOLADO,
            hash=sent.get("hash"), environment=self.intifact.environment, lines=view.lines,
            amount_in_words=view.amount_in_words, issued_by=actor_id)
        await repo.save(doc)
        await register_company(repo, customer, address, email)
        # SUNAT suele responder en segundos: se consulta una vez; si no, queda en curso y lo actualiza el webhook
        # o la revisión periódica.
        if doc.provider_id:
            try:
                await apply_status(repo, doc, await client.document(doc.provider_id))
            except IntifactError:
                logger.info("Comprobante %s encolado; el estado SUNAT llega después", number_of(doc))
        await maybe_notify_customer(repo, doc, self.intifact, self.notifier)
        return doc


async def register_company(repo, customer: tuple[str, str, str], address: Optional[str], email: Optional[str]) -> None:
    """Un RUC nuevo queda en el directorio de clientes de facturación (para autocompletar la próxima vez)."""
    if customer[0] != RUC:
        return
    try:
        if await repo.company_by_ruc(customer[1]) is None:
            await repo.save(InvoicingCompanyModel(ruc=customer[1], legal_name=customer[2][:300], address=address,
                                                  email=email))
    except Exception:
        logger.exception("No se pudo registrar la empresa %s en el directorio", customer[1])


# ---------- Estado SUNAT ----------

async def apply_status(repo, doc: InvoiceDocumentModel, documento: dict) -> InvoiceDocumentModel:
    sunat = documento.get("sunat") if isinstance(documento.get("sunat"), dict) else {}
    new = sunat.get("estado") or documento.get("estado")
    # Pedida la anulación, SUNAT sigue diciendo ACEPTADO hasta resolver el resumen o la baja: queda ANULANDO.
    if new and not (doc.status == ANULANDO and new == ACEPTADO):
        doc.status = str(new)[:20]
    code = sunat.get("codigoRespuesta") or documento.get("codigoRespuesta")
    doc.response_code = str(code)[:10] if code is not None else doc.response_code
    doc.response_description = (sunat.get("descripcionRespuesta") or documento.get("descripcionRespuesta")
                                or documento.get("ultimoError") or doc.response_description)
    if documento.get("hash"):
        doc.hash = str(documento["hash"])[:100]
    doc.updated_at = utcnow()
    return await repo.save(doc)


async def _document(repo, document_id: UUID, *, with_provider: bool = True) -> InvoiceDocumentModel:
    doc = await repo.get_document(document_id)
    if doc is None or (with_provider and not doc.provider_id):
        raise _not_found()
    return doc


@dataclass
class RefreshDocument:
    repo: Any
    intifact: ActiveIntifact
    notifier: Optional[Notifier] = None

    async def execute(self, document_id: UUID) -> InvoiceDocumentModel:
        doc = await _document(self.repo, document_id)
        try:
            await apply_status(self.repo, doc, await self.intifact.client.document(doc.provider_id))
        except IntifactError as exc:
            raise intifact_http_error(exc) from exc
        await maybe_notify_customer(self.repo, doc, self.intifact, self.notifier)
        return doc


@dataclass
class VoidDocument:
    """Factura: comunicación de baja. Boleta: resumen diario con estado anulado. Hasta 7 días."""
    repo: Any
    intifact: ActiveIntifact

    async def execute(self, document_id: UUID, *, reason: str) -> InvoiceDocumentModel:
        doc = await _document(self.repo, document_id)
        if doc.status != ACEPTADO:
            raise _conflict("NOT_VOIDABLE", "Solo se anula un comprobante aceptado por SUNAT.")
        days = (today_lima() - doc.issue_date).days
        if days > DIAS_PARA_ANULAR:
            raise _conflict("VOID_PERIOD_EXPIRED", f"Pasaron {days} días desde la emisión: SUNAT ya no acepta la "
                                                   f"anulación (máximo {DIAS_PARA_ANULAR}). Corresponde una nota "
                                                   "de crédito.")
        reason = reason.strip()[:250]
        body = {"empresaRuc": self.intifact.ruc, "serie": doc.series, "correlativo": doc.number, "motivoBaja": reason}
        boleta = doc.doc_type == TIPO_DOC[BOLETA]
        if not boleta:
            body["tipoDoc"] = doc.doc_type
        try:
            await self.intifact.client.cancel(body, boleta=boleta)
        except IntifactError as exc:
            raise intifact_http_error(exc) from exc
        doc.void_reason = reason
        doc.voided_on = today_lima()
        doc.status = ANULANDO
        doc.updated_at = utcnow()
        await self.repo.save(doc)
        try:
            await apply_status(self.repo, doc, await self.intifact.client.document(doc.provider_id))
        except IntifactError:
            pass
        return doc


FILE_KINDS = ("pdf", "xml", "cdr")


@dataclass
class DocumentFile:
    """PDF (a4 | ticket80 | ticket58), XML firmado o CDR de SUNAT: contenido, tipo y nombre de archivo."""
    repo: Any
    intifact: ActiveIntifact

    async def execute(self, document_id: UUID, kind: str, fmt: Optional[str] = None) -> tuple[bytes, str, str]:
        doc = await _document(self.repo, document_id)
        return await document_file(self.intifact, doc, kind, fmt)


async def document_file(intifact: ActiveIntifact, doc: InvoiceDocumentModel, kind: str,
                        fmt: Optional[str] = None) -> tuple[bytes, str, str]:
    if kind == "cdr" and doc.status not in (ACEPTADO, "RECHAZADO", ANULANDO, ANULADO):
        raise _conflict("CDR_NOT_READY", "SUNAT todavía no devuelve la constancia (CDR) de este comprobante.")
    try:
        content, content_type = await intifact.client.file(doc.provider_id, kind, fmt if kind == "pdf" else None)
    except IntifactError as exc:
        raise intifact_http_error(exc) from exc
    base = f"{intifact.ruc}-{doc.doc_type}-{doc.series}-{doc.number}"
    if kind == "pdf":
        return content, "application/pdf", f"{doc.series}-{doc.number}.pdf"
    ext = "zip" if "zip" in content_type else "xml"
    return content, content_type, f"{'R-' if kind == 'cdr' else ''}{base}.{ext}"


# ---------- Aviso al cliente ----------

async def maybe_notify_customer(repo, doc: InvoiceDocumentModel, intifact: ActiveIntifact,
                                notifier: Optional[Notifier]) -> None:
    """Correo al cliente cuando SUNAT acepta su comprobante. Una sola vez; nunca interrumpe la emisión."""
    if (notifier is None or not intifact.email_customer or doc.status != ACEPTADO or not doc.customer_email
            or doc.customer_notified_at is not None):
        return
    tipo = "boleta" if doc.doc_type == TIPO_DOC[BOLETA] else "factura"
    numero = number_of(doc)
    url = public_pdf_url(intifact.base_url, intifact.ruc, doc.doc_type, doc.series, doc.number)
    nombre = html.escape(doc.customer_name)
    try:
        await notifier(
            to=doc.customer_email,
            subject=f"Tu {tipo} electrónica {numero} de Paku",
            html=(f"<p>Hola {nombre}:</p><p>Te enviamos tu {tipo} electrónica <strong>{html.escape(numero)}</strong> "
                  f"por <strong>S/ {doc.total:.2f}</strong>, emitida el {doc.issue_date:%d/%m/%Y}.</p>"
                  f'<p><a href="{html.escape(url)}">Descargar el comprobante (PDF)</a></p>'
                  "<p>También la encuentras en el detalle de tu servicio en la app de Paku.</p><p>Gracias por "
                  "confiar en Paku.</p>"),
            text=(f"Hola {doc.customer_name}: tu {tipo} electrónica {numero} por S/ {doc.total:.2f}, emitida el "
                  f"{doc.issue_date:%d/%m/%Y}. Descárgala en {url} o en el detalle de tu servicio en la app de Paku."),
            idempotency_key=f"invoice:{doc.id}", template="invoice_issued", user_id=doc.user_id,
            order_id=doc.order_id)
        doc.customer_notified_at = utcnow()
        await repo.save(doc)
    except Exception:
        logger.exception("No se pudo avisar al cliente del comprobante %s", numero)


# ---------- Registro, detalle y pendientes ----------

@dataclass(frozen=True)
class DocumentRow:
    doc: InvoiceDocumentModel
    order_kind: Optional[str]
    pets: Optional[str]


@dataclass(frozen=True)
class RegistryPage:
    items: list[DocumentRow]
    total: int
    accepted_amount: float


@dataclass
class ListRegistry:
    repo: Any

    async def execute(self, *, tipo: Optional[str], status: Optional[str], date_from: Optional[date],
                      date_to: Optional[date], q: Optional[str], environment: Optional[str], page: int,
                      page_size: int) -> RegistryPage:
        docs, total, accepted = await self.repo.registry(
            doc_type=TIPO_DOC.get(tipo) if tipo else None, status=status, date_from=date_from, date_to=date_to,
            q=q, environment=environment, page=page, page_size=page_size)
        return RegistryPage(items=await rows_for(self.repo, docs), total=total, accepted_amount=accepted)


async def rows_for(repo, docs: list[InvoiceDocumentModel]) -> list[DocumentRow]:
    order_ids = [d.order_id for d in docs if d.order_id]
    orders = await repo.orders_by_id(order_ids)
    pets = await repo.order_pet_names(order_ids)
    return [DocumentRow(doc=d, order_kind=order_kind(orders[d.order_id]) if d.order_id in orders else None,
                        pets=pets.get(d.order_id)) for d in docs]


@dataclass
class GetDocument:
    repo: Any

    async def execute(self, document_id: UUID) -> DocumentRow:
        doc = await self.repo.get_document(document_id)
        if doc is None:
            raise _not_found()
        return (await rows_for(self.repo, [doc]))[0]


@dataclass(frozen=True)
class PendingOrder:
    order_id: UUID
    kind: str                         # service | adjustment
    parent_order_id: Optional[UUID]
    created_on: Optional[date]
    order_status: str
    payment_method: Optional[str]
    total: Decimal
    pets: Optional[str]
    user_id: UUID
    customer_name: str
    customer_email: Optional[str]
    customer_dni: Optional[str]
    # Cliente con el que saldría la boleta sin tocar nada (DNI del perfil o consumidor final)
    suggested_doc_type: str
    suggested_doc_number: str
    # Se puede emitir sin datos del admin (lo que hace la emisión automática)
    auto_issuable: bool
    failed_attempts: int = 0
    last_error: Optional[str] = None


@dataclass(frozen=True)
class PendingPage:
    items: list[PendingOrder]
    total: int
    total_amount: Decimal = field(default=Decimal("0"))
    issue_trigger: str = TRIGGER_SERVICE      # con qué momento se armó la lista


def _lima_start(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=LIMA_TZ).astimezone(timezone.utc)


def _pending_row(order, user, pets: Optional[str], failed: list[InvoiceDocumentModel]) -> PendingOrder:
    doc_type, number, _ = profile_customer(user.first_name if user else "", user.last_name if user else "",
                                           user.dni if user else None)
    total = money(order.total_snapshot)
    last = failed[0] if failed else None
    return PendingOrder(
        order_id=order.id, kind=order_kind(order), parent_order_id=order.parent_order_id,
        created_on=_lima_day(order.created_at), order_status=order.status, payment_method=order.payment_method,
        total=total, pets=pets, user_id=order.user_id, customer_name=_full_name(user) or "Usuario eliminado",
        customer_email=user.email if user else None, customer_dni=user.dni if user else None,
        suggested_doc_type=doc_type, suggested_doc_number=number,
        auto_issuable=not is_anonymous(doc_type, number) or total < LIMITE_BOLETA_ANONIMA,
        failed_attempts=len(failed),
        last_error=(f"{number_of(last)} {last.status}: {last.response_description or ''}".strip() if last else None))


@dataclass
class ListPending:
    repo: Any

    async def execute(self, *, date_from: Optional[date] = None, date_to: Optional[date] = None,
                      q: Optional[str] = None, page: int = 1, page_size: int = 25) -> PendingPage:
        user_ids = None
        if q and q.strip():
            user_ids = {u.id for u in await self.repo.search_users(q, limit=500)}
        trigger = await current_issue_trigger(self.repo)
        orders, total = await self.repo.pending_orders(
            created_from=_lima_start(date_from) if date_from else None,
            created_to=_lima_start(date_to + timedelta(days=1)) if date_to else None,
            q_user_ids=user_ids, page=page, page_size=page_size, trigger=trigger)
        return PendingPage(items=await pending_rows(self.repo, orders), total=total,
                           total_amount=sum((money(o.total_snapshot) for o in orders), Decimal("0")),
                           issue_trigger=trigger)


async def pending_rows(repo, orders: list) -> list[PendingOrder]:
    users = await repo.users_by_id([o.user_id for o in orders])
    pets = await repo.order_pet_names([o.id for o in orders])
    rows = []
    for o in orders:
        failed = await repo.documents_for_order(o.id)
        rows.append(_pending_row(o, users.get(o.user_id), pets.get(o.id), failed))
    return rows


@dataclass(frozen=True)
class BatchItem:
    order_id: UUID
    ok: bool                                   # se envió a Intifact (mirar `document.status`: puede ser RECHAZADO)
    document: Optional[InvoiceDocumentModel] = None
    code: Optional[str] = None                 # por qué no se emitió
    message: Optional[str] = None


@dataclass
class IssueBatch:
    """Emite boletas de varias órdenes listas a la vez, con los datos del perfil (DNI o consumidor final por debajo de
    S/ 700), igual que la emisión automática. Las que necesitan datos del admin (factura, boleta de S/ 700 o más sin
    documento) se emiten de a una. Una a la vez y en el orden recibido: un error no detiene las demás."""
    repo: Any
    intifact: ActiveIntifact
    notifier: Optional[Notifier] = None

    async def execute(self, order_ids: list[UUID], *, actor_id: Optional[UUID]) -> list[BatchItem]:
        ids = list(dict.fromkeys(order_ids))
        if not ids:
            raise invalid(InvoicingInvalid("order_ids", "Elige al menos una orden."))
        if len(ids) > MAX_BATCH_ISSUE:
            raise invalid(InvoicingInvalid("order_ids", f"Se emiten hasta {MAX_BATCH_ISSUE} órdenes por envío."))
        orders = await self.repo.orders_by_id(ids)
        rows = {r.order_id: r for r in await pending_rows(self.repo, [orders[i] for i in ids if i in orders])}
        issue = IssueDocument(repo=self.repo, intifact=self.intifact, notifier=self.notifier)
        results = []
        for order_id in ids:
            row = rows.get(order_id)
            if row is None:
                results.append(BatchItem(order_id, False, code="NOT_FOUND", message="Orden no encontrada."))
                continue
            if not row.auto_issuable:
                results.append(BatchItem(order_id, False, code="NEEDS_CUSTOMER_DATA",
                                         message="Necesita el documento del cliente: emítela de a una."))
                continue
            try:
                doc = await issue.execute(order_id, tipo=BOLETA, customer=CustomerInput(), actor_id=actor_id)
                results.append(BatchItem(order_id, True, document=doc))
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
                results.append(BatchItem(order_id, False, code=detail.get("code"), message=detail.get("message")))
        return results


# ---------- Cliente (app) ----------

@dataclass
class CustomerDocuments:
    """Comprobantes de una orden propia, para la app del cliente. Solo los vigentes o anulados (no los fallidos)."""
    repo: Any

    async def execute(self, *, order_id: UUID, user_id: UUID) -> list[InvoiceDocumentModel]:
        order = await self.repo.get_order(order_id)
        if order is None or order.user_id != user_id:
            raise _not_found("Orden no encontrada.")
        return [d for d in await self.repo.documents_for_order(order_id)
                if d.status in (ACEPTADO, ANULANDO, ANULADO, ENCOLADO, "ENVIANDO")]


async def own_document(repo, document_id: UUID, user_id: UUID) -> InvoiceDocumentModel:
    doc = await repo.get_document(document_id)
    if doc is None or doc.user_id != user_id or not doc.provider_id or doc.status not in (ACEPTADO, ANULANDO, ANULADO):
        raise _not_found()
    return doc


def type_name(doc: InvoiceDocumentModel) -> str:
    return NOMBRE_TIPO.get(doc.doc_type, doc.doc_type)
