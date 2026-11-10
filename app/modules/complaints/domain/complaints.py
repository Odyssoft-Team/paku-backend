"""Libro de Reclamaciones virtual (feature 0022).

Reglas de la hoja de reclamación: numeración correlativa por año con un código de identificación, copia inmediata
al consumidor y respuesta del proveedor dentro de 15 días hábiles. Los datos del proveedor se copian en cada hoja
(no cambian si la empresa cambia sus datos después).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

KINDS: dict[str, str] = {"reclamo": "Reclamo", "queja": "Queja"}
KIND_HELP: dict[str, str] = {
    "reclamo": "Disconformidad relacionada a los productos o servicios.",
    "queja": "Disconformidad no relacionada a los productos o servicios, o malestar respecto a la atención al público.",
}
ITEM_TYPES: dict[str, str] = {"servicio": "Servicio", "producto": "Producto"}
DOC_TYPES: dict[str, str] = {"dni": "DNI", "ce": "Carné de extranjería", "pasaporte": "Pasaporte", "ruc": "RUC"}
STATUSES: dict[str, str] = {"received": "Recibido", "answered": "Respondido"}

RECEIVED = "received"
ANSWERED = "answered"
RESPONSE_BUSINESS_DAYS = 15
# Los datos del proveedor y el correo que recibe los avisos salen de los parámetros generales (Configuración →
# Empresa): company_legal_name, company_ruc, company_address y complaints_email.

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{6,20}$")
_DOC_RULES: dict[str, re.Pattern[str]] = {
    "dni": re.compile(r"^\d{8}$"),
    "ruc": re.compile(r"^\d{11}$"),
    "ce": re.compile(r"^[A-Za-z0-9]{8,12}$"),
    "pasaporte": re.compile(r"^[A-Za-z0-9]{6,12}$"),
}
MAX_AMOUNT = Decimal("1000000")
_MULTILINE = frozenset({"detail", "request", "item_description"})


class ComplaintInvalid(Exception):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass
class ComplaintData:
    consumer_name: str
    doc_type: str
    doc_number: str
    email: str
    phone: Optional[str]
    address: Optional[str]
    is_minor: bool
    guardian_name: Optional[str]
    item_type: str
    item_description: str
    order_reference: Optional[str]
    amount_claimed: Optional[Decimal]
    kind: str
    detail: str
    request: str


def format_code(year: int, number: int) -> str:
    """Código de la hoja: correlativo de 6 dígitos y año. Ej.: LR-2026-000001."""
    return f"LR-{year}-{number:06d}"


def add_business_days(start: date, days: int) -> date:
    """Suma días hábiles (lunes a viernes). No descuenta feriados: el plazo calculado nunca es más largo que el real."""
    current, left = start, days
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def _text(raw: dict[str, Any], field: str, label: str, *, min_len: int, max_len: int,
          required: bool = True) -> Optional[str]:
    raw_value = raw.get(field)
    text = "" if raw_value is None else str(raw_value)
    # Los textos largos conservan sus saltos de línea; el resto se lleva a una sola línea.
    value = text.strip() if field in _MULTILINE else " ".join(text.split())
    if not value:
        if required:
            raise ComplaintInvalid(field, f"{label} es obligatorio.")
        return None
    if len(value) < min_len:
        raise ComplaintInvalid(field, f"{label} debe tener al menos {min_len} caracteres.")
    if len(value) > max_len:
        raise ComplaintInvalid(field, f"{label} admite como máximo {max_len} caracteres.")
    return value


def _choice(raw: dict[str, Any], field: str, label: str, options: dict[str, str]) -> str:
    value = str(raw.get(field) or "").strip().lower()
    if value not in options:
        raise ComplaintInvalid(field, f"{label} no es válido.")
    return value


def validate(raw: dict[str, Any]) -> ComplaintData:
    """Valida y normaliza lo que envía el consumidor. Lanza ComplaintInvalid con el campo observado."""
    name = _text(raw, "consumer_name", "El nombre completo", min_len=3, max_len=150)
    doc_type = _choice(raw, "doc_type", "El tipo de documento", DOC_TYPES)
    doc_number = (_text(raw, "doc_number", "El número de documento", min_len=6, max_len=12) or "").replace(" ", "")
    if not _DOC_RULES[doc_type].match(doc_number):
        raise ComplaintInvalid("doc_number", f"El número de {DOC_TYPES[doc_type]} no es válido.")
    email = (_text(raw, "email", "El correo electrónico", min_len=5, max_len=254) or "").lower()
    if not _EMAIL.match(email):
        raise ComplaintInvalid("email", "El correo electrónico no es válido.")
    phone = _text(raw, "phone", "El teléfono", min_len=6, max_len=20, required=False)
    if phone and not _PHONE.match(phone):
        raise ComplaintInvalid("phone", "El teléfono no es válido.")
    address = _text(raw, "address", "El domicilio", min_len=5, max_len=300, required=False)
    is_minor = bool(raw.get("is_minor"))
    guardian = _text(raw, "guardian_name", "El nombre del padre, madre o apoderado", min_len=3, max_len=150,
                     required=is_minor)
    item_type = _choice(raw, "item_type", "El tipo de bien contratado", ITEM_TYPES)
    item_description = _text(raw, "item_description", "La descripción del bien contratado", min_len=3, max_len=500)
    order_reference = _text(raw, "order_reference", "El número de pedido", min_len=1, max_len=60, required=False)

    amount: Optional[Decimal] = None
    raw_amount = raw.get("amount_claimed")
    if raw_amount not in (None, ""):
        try:
            amount = Decimal(str(raw_amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise ComplaintInvalid("amount_claimed", "El monto reclamado no es válido.")
        if amount <= 0 or amount > MAX_AMOUNT:
            raise ComplaintInvalid("amount_claimed", "El monto reclamado no es válido.")

    kind = _choice(raw, "kind", "El tipo de reclamación", KINDS)
    detail = _text(raw, "detail", "El detalle", min_len=10, max_len=3000)
    request = _text(raw, "request", "El pedido", min_len=5, max_len=1500)
    return ComplaintData(
        consumer_name=name or "", doc_type=doc_type, doc_number=doc_number, email=email, phone=phone,
        address=address, is_minor=is_minor, guardian_name=guardian if is_minor else None, item_type=item_type,
        item_description=item_description or "", order_reference=order_reference, amount_claimed=amount, kind=kind,
        detail=detail or "", request=request or "",
    )


def validate_response(text: Any) -> str:
    value = str(text or "").strip()
    if len(value) < 10:
        raise ComplaintInvalid("response", "La respuesta debe tener al menos 10 caracteres.")
    if len(value) > 5000:
        raise ComplaintInvalid("response", "La respuesta admite como máximo 5000 caracteres.")
    return value
