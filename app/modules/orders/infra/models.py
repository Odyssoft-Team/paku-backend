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

    # Orden que originó esta (solo presente en "órdenes de ajuste" por recálculo de precio)
    parent_order_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=True
    )

    # Pago: se actualiza al llamar POST /orders/{id}/pay (u orquestado por el cronjob de
    # reconciliación cuando queda en "verifying")
    # payment_status: pending → verifying → paid | failed
    # culqi_charge_id: chr_(test|live)_XXXXXXXXXXXXXXXX — presente solo cuando paid vía Culqi
    # payment_method: card | yape | cash — cash se confirma directo por el ally, sin Culqi
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    culqi_charge_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

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


class OrderPetModel(Base):
    """
    Tabla puente: qué mascota(s) cubre una orden. Se puebla al crear la orden a partir
    del carrito, extrayendo los pet_id de items_snapshot[].meta.pet_id (una orden puede
    incluir servicios para más de una mascota). Existe para poder consultar directo
    "¿qué orden(es) tiene esta mascota?" sin parsear el JSON de items_snapshot.
    """
    __tablename__ = "order_pets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    pet_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)


async def ensure_orders_schema(engine: AsyncEngine) -> None:
    # DDL gestionado por Alembic. No crear tablas aquí.
    pass
