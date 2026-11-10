"""Libro de Reclamaciones (feature 0022): registrar una hoja, listarla y responderla."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.core.timezone import LIMA_TZ
from app.modules.complaints.domain.complaints import (
    ANSWERED,
    DOC_TYPES,
    ITEM_TYPES,
    KINDS,
    RECEIVED,
    RESPONSE_BUSINESS_DAYS,
    ComplaintInvalid,
    add_business_days,
    validate,
    validate_response,
)
from app.modules.complaints.infra.models import ComplaintModel, utcnow
from app.modules.general_settings.domain.settings import resolve

logger = logging.getLogger(__name__)

# (to, subject, html, text, idempotency_key, template) -> None. Nunca debe lanzar (ver messaging.send_email).
Notifier = Callable[..., Awaitable[Any]]


def invalid(exc: ComplaintInvalid) -> HTTPException:
    return HTTPException(status_code=422,
                         detail={"code": "COMPLAINT_INVALID", "message": exc.message, "field": exc.field})


def _lima(dt: datetime) -> str:
    return dt.astimezone(LIMA_TZ).strftime("%d/%m/%Y %H:%M")


def sheet_rows(c: ComplaintModel) -> list[tuple[str, str]]:
    """Contenido de la hoja, en el orden en que se muestra (correo y admin)."""
    rows = [
        ("Hoja N.°", c.code),
        ("Fecha", _lima(c.created_at)),
        ("Proveedor", f"{c.provider_legal_name} — RUC {c.provider_ruc}"),
        ("Domicilio del proveedor", c.provider_address),
        ("Consumidor", c.consumer_name),
        ("Documento", f"{DOC_TYPES.get(c.doc_type, c.doc_type)} {c.doc_number}"),
        ("Correo", c.email),
    ]
    if c.phone:
        rows.append(("Teléfono", c.phone))
    if c.address:
        rows.append(("Domicilio", c.address))
    if c.is_minor:
        rows.append(("Padre, madre o apoderado", c.guardian_name or ""))
    rows += [("Bien contratado", f"{ITEM_TYPES.get(c.item_type, c.item_type)}: {c.item_description}")]
    if c.order_reference:
        rows.append(("Número de pedido", c.order_reference))
    if c.amount_claimed is not None:
        rows.append(("Monto reclamado", f"S/ {c.amount_claimed:.2f}"))
    rows += [
        ("Tipo", KINDS.get(c.kind, c.kind)),
        ("Detalle", c.detail),
        ("Pedido del consumidor", c.request),
        ("Plazo de respuesta", f"Hasta el {c.response_due.strftime('%d/%m/%Y')} ({RESPONSE_BUSINESS_DAYS} días hábiles)"),
    ]
    return rows


def _html(intro: str, rows: list[tuple[str, str]], outro: str = "") -> str:
    cells = "".join(
        f'<tr><td style="padding:6px 10px;border:1px solid #ddd;font-weight:600;vertical-align:top;width:35%">'
        f'{escape(k)}</td><td style="padding:6px 10px;border:1px solid #ddd;white-space:pre-wrap">{escape(v)}</td></tr>'
        for k, v in rows
    )
    return (f'<div style="font-family:Arial,sans-serif;font-size:14px;color:#222">'
            f'<p>{escape(intro)}</p><table style="border-collapse:collapse;width:100%">{cells}</table>'
            f'{f"<p>{escape(outro)}</p>" if outro else ""}</div>')


def _text(intro: str, rows: list[tuple[str, str]], outro: str = "") -> str:
    body = "\n".join(f"{k}: {v}" for k, v in rows)
    return f"{intro}\n\n{body}" + (f"\n\n{outro}" if outro else "")


async def _safe(notify: Notifier, **kw: Any) -> None:
    """La hoja ya quedó guardada: una falla al encolar el correo no debe perderla (queda en el log)."""
    try:
        await notify(**kw)
    except Exception:
        logger.exception("No se pudo registrar el correo %s", kw.get("idempotency_key"))


LEGAL_NOTE = ("La formulación del reclamo no impide acudir a otras vías de solución de controversias ni es requisito "
              "previo para interponer una denuncia ante el INDECOPI.")


@dataclass
class SubmitComplaint:
    repo: Any
    settings_repo: Any
    notify: Notifier
    now: Callable[[], datetime] = field(default=utcnow)

    async def execute(self, raw: dict[str, Any], *, user_id: Optional[UUID] = None) -> ComplaintModel:
        try:
            data = validate(raw)
        except ComplaintInvalid as exc:
            raise invalid(exc) from exc
        company = resolve(await self.settings_repo.get_all())
        now = self.now()
        today = now.astimezone(LIMA_TZ).date()
        complaint = ComplaintModel(
            id=uuid4(), created_at=now, user_id=user_id, status=RECEIVED,
            response_due=add_business_days(today, RESPONSE_BUSINESS_DAYS),
            consumer_name=data.consumer_name, doc_type=data.doc_type, doc_number=data.doc_number, email=data.email,
            phone=data.phone, address=data.address, is_minor=data.is_minor, guardian_name=data.guardian_name,
            item_type=data.item_type, item_description=data.item_description, order_reference=data.order_reference,
            amount_claimed=data.amount_claimed, kind=data.kind, detail=data.detail, request=data.request,
            provider_legal_name=company["company_legal_name"], provider_ruc=company["company_ruc"],
            provider_address=company["company_address"],
        )
        complaint = await self.repo.add_with_next_number(complaint, year=today.year)

        rows = sheet_rows(complaint)
        kind = KINDS[complaint.kind].lower()
        intro = (f"Hola, {complaint.consumer_name}. Registramos tu {kind} en nuestro Libro de Reclamaciones. "
                 f"Esta es la copia de tu hoja:")
        await _safe(self.notify, to=complaint.email, subject=f"Copia de tu hoja de reclamación {complaint.code}",
                          html=_html(intro, rows, LEGAL_NOTE), text=_text(intro, rows, LEGAL_NOTE),
                          idempotency_key=f"complaint:copy:{complaint.id}", template="complaint_copy")
        staff_intro = f"Se registró una nueva hoja en el Libro de Reclamaciones ({KINDS[complaint.kind]})."
        await _safe(self.notify, to=company["complaints_email"],
                          subject=f"Nuevo {kind} {complaint.code} — responder hasta el "
                                  f"{complaint.response_due.strftime('%d/%m/%Y')}",
                          html=_html(staff_intro, rows), text=_text(staff_intro, rows),
                          idempotency_key=f"complaint:notify:{complaint.id}", template="complaint_notify")
        return complaint


@dataclass
class ListComplaints:
    repo: Any

    async def execute(self, *, status: Optional[str], limit: int, offset: int) -> tuple[list[ComplaintModel], int]:
        return await self.repo.list(status=status, limit=limit, offset=offset)


@dataclass
class GetComplaint:
    repo: Any

    async def execute(self, complaint_id: UUID) -> ComplaintModel:
        complaint = await self.repo.get(complaint_id)
        if complaint is None:
            raise HTTPException(status_code=404,
                                detail={"code": "COMPLAINT_NOT_FOUND", "message": "La hoja no existe."})
        return complaint


@dataclass
class AnswerComplaint:
    repo: Any
    notify: Notifier
    now: Callable[[], datetime] = field(default=utcnow)

    async def execute(self, complaint_id: UUID, text: Any, *, actor_id: UUID) -> ComplaintModel:
        complaint = await GetComplaint(repo=self.repo).execute(complaint_id)
        if complaint.status == ANSWERED:
            raise HTTPException(status_code=409, detail={"code": "COMPLAINT_ALREADY_ANSWERED",
                                                         "message": "Esta hoja ya fue respondida."})
        try:
            response = validate_response(text)
        except ComplaintInvalid as exc:
            raise invalid(exc) from exc
        complaint.response = response
        complaint.status = ANSWERED
        complaint.responded_at = self.now()
        complaint.responded_by = actor_id
        complaint = await self.repo.save(complaint)

        rows = [("Hoja N.°", complaint.code), ("Pedido del consumidor", complaint.request),
                ("Respuesta del proveedor", response)]
        intro = f"Hola, {complaint.consumer_name}. Esta es nuestra respuesta a tu hoja de reclamación {complaint.code}:"
        await _safe(self.notify, to=complaint.email, subject=f"Respuesta a tu hoja de reclamación {complaint.code}",
                          html=_html(intro, rows, LEGAL_NOTE), text=_text(intro, rows, LEGAL_NOTE),
                          idempotency_key=f"complaint:answer:{complaint.id}", template="complaint_answer")
        return complaint
