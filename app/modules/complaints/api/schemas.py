from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ComplaintIn(BaseModel):
    """Lo que llena el consumidor. La validación de contenido (largos, documento, correo) la hace el dominio y
    responde 422 `COMPLAINT_INVALID` con `field`."""
    consumer_name: str = ""
    doc_type: str = Field("", description="dni | ce | pasaporte | ruc")
    doc_number: str = ""
    email: str = ""
    phone: Optional[str] = None
    address: Optional[str] = None
    is_minor: bool = False
    guardian_name: Optional[str] = Field(None, description="Obligatorio si is_minor")
    item_type: str = Field("", description="servicio | producto")
    item_description: str = ""
    order_reference: Optional[str] = None
    amount_claimed: Optional[Decimal] = None
    kind: str = Field("", description="reclamo | queja")
    detail: str = ""
    request: str = ""


class ComplaintReceiptOut(BaseModel):
    """Constancia para el consumidor (la misma información llega a su correo)."""
    id: UUID
    code: str
    created_at: datetime
    response_due: date
    email: str
    provider_legal_name: str
    provider_ruc: str
    provider_address: str


class SheetRowOut(BaseModel):
    label: str
    value: str


class ComplaintSummaryOut(BaseModel):
    id: UUID
    code: str
    created_at: datetime
    kind: str
    kind_label: str
    consumer_name: str
    email: str
    status: str
    status_label: str
    response_due: date
    overdue: bool = Field(description="Sin responder y con el plazo vencido")


class ComplaintDetailOut(ComplaintSummaryOut):
    sheet: list[SheetRowOut] = Field(description="Hoja completa, en orden de lectura")
    response: Optional[str] = None
    responded_at: Optional[datetime] = None
    responded_by: Optional[UUID] = None


class ComplaintListOut(BaseModel):
    items: list[ComplaintSummaryOut]
    total: int


class ComplaintAnswerIn(BaseModel):
    response: str = ""
