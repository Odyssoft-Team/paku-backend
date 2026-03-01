from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="created")

    items_snapshot: Mapped[Any] = mapped_column(JSON, nullable=False)
    total_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="PEN")
    delivery_address_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Asignación desnormalizada para queries rápidas (ej: órdenes del ally X)
    # El detalle completo vive en order_assignments
    ally_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Reserva que originó esta orden (puede ser null si se crea sin hold)
    hold_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class OrderAssignmentModel(Base):
    """
    Registro de asignación de un ally a una orden por parte del administrador.
    Cada reasignación genera un nuevo registro (historial completo).
    """
    __tablename__ = "order_assignments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    ally_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


async def ensure_orders_schema(engine: AsyncEngine) -> None:
    # DDL gestionado por Alembic. No crear tablas aquí.
    pass
