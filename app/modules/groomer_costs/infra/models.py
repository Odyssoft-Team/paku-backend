from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Index, JSON, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GroomerCostProfileModel(Base):
    """Registro de costo de un groomer vigente desde una fecha (feature 0012)."""
    __tablename__ = "groomer_cost_profiles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    groomer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)   # [{label, kind, value}]
    monthly_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    driving_rest_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_groomer_cost_profiles_groomer_date", "groomer_id", "effective_from", unique=True),
    )
