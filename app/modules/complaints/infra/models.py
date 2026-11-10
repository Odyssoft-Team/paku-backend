from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ComplaintCounterModel(Base):
    """Último correlativo usado por año (feature 0022)."""
    __tablename__ = "complaint_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ComplaintModel(Base):
    """Hoja del Libro de Reclamaciones (feature 0022). Lo que envió el consumidor no se modifica; solo se agrega
    la respuesta del proveedor."""
    __tablename__ = "complaints"
    __table_args__ = (UniqueConstraint("year", "number", name="uq_complaints_year_number"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)

    consumer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(12), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    is_minor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guardian_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_description: Mapped[str] = mapped_column(Text, nullable=False)
    order_reference: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    amount_claimed: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    request: Mapped[str] = mapped_column(Text, nullable=False)

    provider_legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_ruc: Mapped[str] = mapped_column(String(11), nullable=False)
    provider_address: Mapped[str] = mapped_column(String(300), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")
    response_due: Mapped[date] = mapped_column(Date, nullable=False)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
