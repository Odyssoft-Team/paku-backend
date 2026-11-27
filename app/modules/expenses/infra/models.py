from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VehicleModel(Base):
    """Vehículo de la empresa (feature 0026): se le ligan sus gastos."""
    __tablename__ = "vehicles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    plate: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True)
    brand: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ExpenseModel(Base):
    """Gasto operativo (feature 0026). No se borra: se anula con motivo."""
    __tablename__ = "expenses"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)                # one_time | monthly | annual
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    igv_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)       # sin IGV
    vehicle_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("vehicles.id"), nullable=True, index=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    document: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)    # n.º de comprobante
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_expenses_start_date", "start_date"),)
