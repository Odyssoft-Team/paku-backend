from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

DocType = Literal["BOLETA", "FACTURA"]
# Catálogo SUNAT 06: 1 DNI, 4 carné de extranjería, 6 RUC, 7 pasaporte
CustomerDocType = Literal["1", "4", "6", "7"]
IssueTrigger = Literal["service", "payment"]
TRIGGER_HELP = ("Cuándo una orden pagada queda lista para emitir: service = al realizarse el servicio (la boleta sale con "
                "la fecha del servicio); payment = al confirmarse el pago. La emisión automática emite en ese momento.")


# ---------- Integración ----------

class ReadinessOut(BaseModel):
    company_ruc: Optional[str] = Field(None, description="RUC de Paku en Parámetros generales.")
    company_name: Optional[str] = None
    company_legal_name: Optional[str] = None
    igv_percent: float
    customers: int = Field(..., description="Clientes activos.")
    customers_with_dni: int = Field(..., description="De ellos, con DNI registrado (boleta sin pedir datos).")
    boleta_series: Optional[str] = Field(None, description="Serie activa de boletas; sin ella no se emiten.")
    factura_series: Optional[str] = None


class IntifactIntegrationOut(BaseModel):
    enabled: bool
    configured: bool
    api_url: str
    api_key_mask: Optional[str] = Field(None, description="Nunca la key completa: fact_test_…abcd.")
    environment: Optional[Literal["test", "live"]] = Field(
        None, description="test = SUNAT beta (sin valor fiscal); live = producción. Lo decide la key.")
    company_ruc: Optional[str] = Field(None, description="RUC emisor en Intifact (en pruebas, el de la sandbox).")
    webhook_secret_mask: Optional[str] = None
    webhook_path: str = Field("/invoicing/webhook", description="Ruta a registrar en el portal de Intifact.")
    auto_issue: bool
    issue_trigger: IssueTrigger = Field(..., description=TRIGGER_HELP)
    email_customer: bool
    status: str = Field(..., description="not_configured | disabled | active | error (falló la última prueba)")
    last_test_at: Optional[datetime] = None
    last_test_ok: Optional[bool] = None
    last_test_error: Optional[str] = None
    encryption_ready: bool
    updated_at: Optional[datetime] = None
    updated_by: Optional[UUID] = None
    readiness: ReadinessOut


class IntifactIntegrationIn(BaseModel):
    enabled: bool = False
    api_key: Optional[str] = Field(None, description="fact_test_… o fact_live_…. Vacío: se conserva la guardada.")
    company_ruc: Optional[str] = Field(None, description="RUC emisor de la cuenta de Intifact.")
    webhook_secret: Optional[str] = Field(None, description="El que muestra el portal. Vacío: se conserva.")
    auto_issue: bool = False
    issue_trigger: Optional[IssueTrigger] = Field(None, description=TRIGGER_HELP + " Ausente: se conserva.")
    email_customer: bool = True


class ConnectionTestOut(BaseModel):
    ok: bool
    message: str


# ---------- Series ----------

class SeriesOut(BaseModel):
    id: UUID
    type: DocType
    doc_type: str
    series: str
    first_number: int
    is_active: bool
    issued: int = Field(..., description="Emitidos con la serie en el ambiente actual.")
    last_number: Optional[int] = None
    next_number: int


class SeriesCreateIn(BaseModel):
    type: DocType
    series: str = Field(..., min_length=4, max_length=4)
    first_number: int = Field(1, ge=1, le=99_999_999)
    is_active: bool = True


class SeriesUpdateIn(BaseModel):
    series: Optional[str] = Field(None, min_length=4, max_length=4)
    first_number: Optional[int] = Field(None, ge=1, le=99_999_999)
    is_active: Optional[bool] = None


# ---------- Emisión ----------

class IssueIn(BaseModel):
    """Datos del cliente. En una boleta, vacíos = los del perfil (DNI) o consumidor final por debajo de S/ 700."""
    type: DocType = "BOLETA"
    customer_doc_type: Optional[CustomerDocType] = None
    customer_doc_number: Optional[str] = Field(None, max_length=20)
    customer_name: Optional[str] = Field(None, max_length=255)
    customer_address: Optional[str] = Field(None, max_length=500)
    customer_email: Optional[str] = Field(None, max_length=255)


class LineOut(BaseModel):
    description: str
    quantity: float
    unit_value: Decimal = Field(..., description="Sin IGV.")
    unit_price: Decimal = Field(..., description="Con IGV.")
    igv: Decimal
    total: Decimal


class PreviewOut(BaseModel):
    type: DocType
    number: str = Field(..., description="El que tendría si se emite ahora.")
    issue_date: date
    customer_doc_type: str
    customer_doc_number: str
    customer_name: str
    customer_address: Optional[str] = None
    customer_email: Optional[str] = None
    lines: list[LineOut]
    taxable_amount: Decimal
    igv: Decimal
    total: Decimal
    amount_in_words: Optional[str] = None
    environment: str


class DocumentOut(BaseModel):
    id: UUID
    order_id: Optional[UUID] = None
    order_kind: Optional[Literal["service", "adjustment"]] = None
    pets: Optional[str] = None
    type: DocType
    doc_type: str
    series: str
    number: str
    full_number: str
    issue_date: date
    customer_doc_type: str
    customer_doc_number: str
    customer_name: str
    customer_address: Optional[str] = None
    customer_email: Optional[str] = None
    taxable_amount: Decimal
    igv: Decimal
    total: Decimal
    currency: str
    status: str = Field(..., description="ENCOLADO, ACEPTADO, RECHAZADO, ANULANDO, ANULADO, ERROR, COLA_FALLIDA…")
    response_code: Optional[str] = None
    response_description: Optional[str] = None
    environment: Literal["test", "live"]
    automatic: bool = Field(..., description="Emitido por la emisión automática.")
    customer_notified_at: Optional[datetime] = None
    days_left_to_void: int = Field(..., description="Días que quedan para anular (0 = corresponde nota de crédito).")
    created_at: datetime


class DocumentDetailOut(DocumentOut):
    lines: list[LineOut]
    amount_in_words: Optional[str] = None
    hash: Optional[str] = None
    void_reason: Optional[str] = None
    voided_on: Optional[date] = None


class RegistryOut(BaseModel):
    items: list[DocumentOut]
    total: int
    accepted_amount: Decimal = Field(..., description="Suma de los aceptados que cumplen el filtro (todas las páginas).")


class PendingOut(BaseModel):
    order_id: UUID
    kind: Literal["service", "adjustment"]
    parent_order_id: Optional[UUID] = None
    created_on: Optional[date] = None
    order_status: str
    payment_method: Optional[str] = None
    total: Decimal
    pets: Optional[str] = None
    user_id: UUID
    customer_name: str
    customer_email: Optional[str] = None
    customer_dni: Optional[str] = None
    suggested_doc_type: str
    suggested_doc_number: str = Field(..., description="00000000 = consumidor final.")
    auto_issuable: bool = Field(..., description="Se emite sin datos del admin (lo que hace la emisión automática).")
    failed_attempts: int
    last_error: Optional[str] = None


class PendingPageOut(BaseModel):
    items: list[PendingOut]
    total: int
    total_amount: Decimal = Field(..., description="Suma de la página.")
    issue_trigger: IssueTrigger = Field(..., description="Momento con el que se armó la lista. " + TRIGGER_HELP)


class IssueBatchIn(BaseModel):
    order_ids: list[UUID] = Field(..., min_length=1, max_length=50)


class IssueBatchItemOut(BaseModel):
    order_id: UUID
    ok: bool = Field(..., description="Se envió a Intifact; el estado SUNAT está en `document.status`.")
    document: Optional[DocumentOut] = None
    code: Optional[str] = Field(None, description="Por qué no se emitió: NEEDS_CUSTOMER_DATA, ORDER_NOT_READY, "
                                                  "DOCUMENT_EXISTS, INTIFACT_ERROR…")
    message: Optional[str] = None


class IssueBatchOut(BaseModel):
    items: list[IssueBatchItemOut]
    issued: int
    failed: int


class VoidIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=250)


# ---------- Directorio ----------

class HistoryOut(BaseModel):
    boletas: int
    facturas: int
    total: Decimal
    last: Optional[date] = None


class DirectoryRowOut(BaseModel):
    origin: Literal["USER", "COMPANY"]
    id: UUID
    name: str
    trade_name: Optional[str] = None
    doc_type: str
    doc_number: str
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    history: HistoryOut


class DirectoryPageOut(BaseModel):
    items: list[DirectoryRowOut]
    total: int


class SuggestionOut(BaseModel):
    origin: Literal["USER", "COMPANY"]
    id: UUID
    doc_type: str
    doc_number: str
    name: str
    address: Optional[str] = None
    email: Optional[str] = None
    detail: str


class CompanyIn(BaseModel):
    ruc: str = Field(..., pattern=r"^(10|15|16|17|20)\d{9}$")
    legal_name: str = Field(..., min_length=1, max_length=300)
    trade_name: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)
    notes: Optional[str] = None


class CompanyUpdateIn(BaseModel):
    legal_name: Optional[str] = Field(None, min_length=1, max_length=300)
    trade_name: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)
    notes: Optional[str] = None


class CompanyOut(BaseModel):
    id: UUID
    ruc: str
    legal_name: str
    trade_name: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


# ---------- Contabilidad ----------

class AccountingMonthOut(BaseModel):
    month: str = Field(..., description="AAAA-MM")
    boletas: int
    facturas: int
    voided: int
    total: Decimal = Field(..., description="Aceptados, sin anulados.")


# ---------- App del cliente ----------

class CustomerDocumentOut(BaseModel):
    id: UUID
    type: DocType
    full_number: str
    issue_date: date
    total: Decimal
    status: str
    pdf_available: bool = Field(..., description="Con ACEPTADO (o anulado) se descarga el PDF.")
