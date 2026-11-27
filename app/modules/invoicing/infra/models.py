from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InvoicingProviderModel(Base):
    """Proveedor de facturación electrónica. Una fila por proveedor (`intifact`).

    La API key y el secreto del webhook se guardan cifrados (Fernet, `app/core/crypto.py`); el admin solo ve la
    máscara. `api_url` es la URL base de la API. `boleta_series` es de Nubefact (0020, abandonada): ya no se usa;
    las series viven en `invoicing_series`.
    """
    __tablename__ = "invoicing_providers"

    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    api_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_mask: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    boleta_series: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    # RUC emisor en Intifact. En pruebas es el de la empresa sandbox que crea el portal, no el de Paku.
    company_ruc: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    webhook_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    webhook_secret_mask: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Emite solo las boletas de órdenes pagadas que no necesitan datos del admin (regla 10 del spec 0023).
    auto_issue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Cuándo una orden queda lista para emitir: service (al realizarse el servicio) | payment (al confirmarse el pago).
    issue_trigger: Mapped[str] = mapped_column(String(10), nullable=False, default="service", server_default="service")
    # Avisa al cliente por correo cuando SUNAT acepta su comprobante.
    email_customer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_test_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class InvoicingSeriesModel(Base):
    """Serie con la que se emite cada tipo de comprobante. Una activa por tipo.

    `first_number`: primer correlativo a usar. Sirve para seguir una serie que ya usó otro sistema sin repetir
    números; con una serie nueva queda en 1.
    """
    __tablename__ = "invoicing_series"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    doc_type: Mapped[str] = mapped_column(String(2), nullable=False)          # 03 boleta, 01 factura
    series: Mapped[str] = mapped_column(String(4), nullable=False, unique=True)
    first_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class InvoiceDocumentModel(Base):
    """Comprobante electrónico emitido con Intifact: boleta (03) o factura (01) de una orden pagada."""
    __tablename__ = "invoice_documents"
    __table_args__ = (UniqueConstraint("environment", "doc_type", "series", "number",
                                       name="uq_invoice_documents_number"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    doc_type: Mapped[str] = mapped_column(String(2), nullable=False)
    series: Mapped[str] = mapped_column(String(4), nullable=False)
    number: Mapped[str] = mapped_column(String(8), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    customer_doc_type: Mapped[str] = mapped_column(String(1), nullable=False)
    customer_doc_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)   # valor de venta (sin IGV)
    igv: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    # Intifact: id del documento, estado SUNAT y respuesta
    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ENCOLADO", index=True)
    response_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    response_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    environment: Mapped[str] = mapped_column(String(4), nullable=False, default="test")   # test | live
    # Lo emitido, para mostrarlo tal cual: líneas y monto en letras
    lines: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    amount_in_words: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Anulación (comunicación de baja o resumen diario)
    void_reason: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    voided_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    issued_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)   # None = automática
    customer_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class InvoicingCompanyModel(Base):
    """Cliente con RUC que no es un usuario de la app con su RUC (p. ej. la empresa que pide factura).

    Los usuarios no se copian aquí: el directorio de clientes de facturación los junta sin duplicarlos.
    """
    __tablename__ = "invoicing_companies"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ruc: Mapped[str] = mapped_column(String(11), nullable=False, unique=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(300), nullable=False)
    trade_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
