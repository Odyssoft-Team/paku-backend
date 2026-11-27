"""Clientes de facturación (feature 0023): un directorio que junta, sin copiarlos,

- usuarios de la app con documento (DNI, carné o pasaporte en su perfil);
- empresas con RUC (`invoicing_companies`): las que pidieron factura; se registran solas al emitir con un RUC nuevo.

El historial (boletas, facturas, monto, último comprobante) sale de los comprobantes aceptados. Los datos del usuario
se editan en su perfil; aquí solo se crean y editan las empresas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException

from app.modules.invoicing.app.config import invalid
from app.modules.invoicing.domain.intifact import CE, DNI, RUC, InvoicingInvalid, check_ruc
from app.modules.invoicing.infra.models import InvoicingCompanyModel, utcnow


@dataclass
class History:
    boletas: int = 0
    facturas: int = 0
    total: Decimal = Decimal("0")
    last: Optional[date] = None


@dataclass(frozen=True)
class DirectoryRow:
    origin: str                      # USER | COMPANY
    id: UUID
    name: str
    trade_name: Optional[str]
    doc_type: str                    # código SUNAT: 1, 4, 6, 7
    doc_number: str
    address: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    history: History = field(default_factory=History)


@dataclass(frozen=True)
class DirectoryPage:
    items: list[DirectoryRow]
    total: int


def user_document(dni: Optional[str]) -> Optional[tuple[str, str]]:
    """El perfil solo tiene un campo «dni»: 8 dígitos es DNI; otro alfanumérico de 6 a 12, carné de extranjería."""
    number = re.sub(r"\s", "", dni or "").upper()
    if re.fullmatch(r"\d{8}", number) and number != "00000000":
        return DNI, number
    if re.fullmatch(r"[A-Z0-9]{6,12}", number):
        return CE, number
    return None


def _user_row(u) -> Optional[DirectoryRow]:
    doc = user_document(u.dni)
    if doc is None:
        return None
    return DirectoryRow(origin="USER", id=u.id, name=f"{u.first_name} {u.last_name}".strip(), trade_name=None,
                        doc_type=doc[0], doc_number=doc[1], address=u.address_line, email=u.email, phone=u.phone,
                        notes=None)


def _company_row(c: InvoicingCompanyModel) -> DirectoryRow:
    return DirectoryRow(origin="COMPANY", id=c.id, name=c.legal_name, trade_name=c.trade_name, doc_type=RUC,
                        doc_number=c.ruc, address=c.address, email=c.email, phone=c.phone, notes=c.notes)


async def _histories(repo, numbers: set[str]) -> dict[str, History]:
    out: dict[str, History] = {}
    for number, doc_type, count, total, last in await repo.history_by_doc(numbers):
        h = out.setdefault(number, History())
        if doc_type == "03":
            h.boletas += count
        else:
            h.facturas += count
        h.total += Decimal(str(total or 0))
        h.last = max(filter(None, [h.last, last]), default=None)
    return out


@dataclass
class ListDirectory:
    repo: Any

    async def execute(self, *, q: Optional[str], origin: Optional[str], with_documents: bool, page: int,
                      page_size: int) -> DirectoryPage:
        rows: list[DirectoryRow] = []
        if origin in (None, "USER"):
            rows += [r for r in (_user_row(u) for u in await self.repo.users_with_document(q)) if r]
        if origin in (None, "COMPANY"):
            rows += [_company_row(c) for c in await self.repo.companies(q)]
        histories = await _histories(self.repo, {r.doc_number for r in rows})
        for r in rows:
            h = histories.get(r.doc_number)
            if h:
                r.history.boletas, r.history.facturas, r.history.total, r.history.last = (
                    h.boletas, h.facturas, h.total, h.last)
        if with_documents:
            rows = [r for r in rows if r.history.boletas or r.history.facturas]
        # Primero quien tiene comprobantes más recientes; luego por nombre
        rows.sort(key=lambda r: (r.history.last is None, -(r.history.last.toordinal() if r.history.last else 0),
                                 r.name.upper()))
        start = (page - 1) * page_size
        return DirectoryPage(items=rows[start:start + page_size], total=len(rows))


@dataclass(frozen=True)
class Suggestion:
    origin: str
    id: UUID
    doc_type: str
    doc_number: str
    name: str
    address: Optional[str]
    email: Optional[str]
    detail: str


@dataclass
class SearchCustomers:
    """Autocompletar al emitir: por número de documento, nombre o correo."""
    repo: Any

    async def execute(self, q: str, limit: int = 8) -> list[Suggestion]:
        if not q or len(q.strip()) < 2:
            return []
        out: list[Suggestion] = []
        for u in await self.repo.search_users(q, limit=20, with_document=True):
            row = _user_row(u)
            if row:
                out.append(Suggestion(origin="USER", id=u.id, doc_type=row.doc_type, doc_number=row.doc_number,
                                      name=row.name, address=row.address, email=row.email,
                                      detail="Cliente · " + ("DNI" if row.doc_type == DNI else "Carné de extranjería")))
        for c in await self.repo.companies(q):
            out.append(Suggestion(origin="COMPANY", id=c.id, doc_type=RUC, doc_number=c.ruc, name=c.legal_name,
                                  address=c.address, email=c.email,
                                  detail="Empresa" + (f" · {c.trade_name}" if c.trade_name else "")))
        text = q.strip()
        out.sort(key=lambda s: (s.doc_number != text, not s.doc_number.startswith(text), s.name.upper()))
        return out[:limit]


COMPANY_FIELDS = ("legal_name", "trade_name", "address", "email", "phone", "notes")


@dataclass
class SaveCompany:
    repo: Any

    async def create(self, *, ruc: str, **data: Any) -> InvoicingCompanyModel:
        try:
            ruc = check_ruc(ruc, "ruc")
        except InvoicingInvalid as exc:
            raise invalid(exc) from exc
        if await self.repo.company_by_ruc(ruc):
            raise HTTPException(status_code=409, detail={"code": "COMPANY_EXISTS",
                                                         "message": "Ya hay una empresa con ese RUC."})
        company = InvoicingCompanyModel(ruc=ruc, **{k: v for k, v in data.items() if k in COMPANY_FIELDS})
        return await self.repo.save(company)

    async def update(self, company_id: UUID, **data: Any) -> InvoicingCompanyModel:
        company = await self.repo.get_company(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Empresa no encontrada."})
        for key, value in data.items():
            if key in COMPANY_FIELDS:
                setattr(company, key, value)
        company.updated_at = utcnow()
        return await self.repo.save(company)
