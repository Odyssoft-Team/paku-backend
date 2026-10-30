from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Identity, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupplyModel(Base):
    """Maestro de insumos (feature 0009)."""
    __tablename__ = "inventory_supplies"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    sku: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    purchase_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    purchase_content: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    consumption_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    tracks_lot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tracks_expiry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class MovementModel(Base):
    """Movimiento de stock. No se edita ni se borra: los errores se corrigen con un ajuste."""
    __tablename__ = "inventory_movements"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    seq: Mapped[int] = mapped_column(Integer, Identity(), nullable=False, unique=True)  # MOV-0001
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    supply_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_supplies.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)       # con signo
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)      # costo por unidad al registrarlo
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    order_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    recipe_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    recipe_cell_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    lot: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    expires_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)  # null = sistema
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_inventory_movements_occurred_on", "occurred_on"),
        Index("ix_inventory_movements_order_type", "order_id", "type"),
    )


class RecipeModel(Base):
    """Tabla de consumo de un servicio o adicional. Cada versión es una fila; la vigente tiene is_current."""
    __tablename__ = "inventory_recipes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)          # product | addon
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_inventory_recipes_target_version", "target_id", "version", unique=True),
    )


class RecipeCellModel(Base):
    """Celda de la tabla: tipo de pelaje (o "mestizo") × tramo de peso, como en los precios."""
    __tablename__ = "inventory_recipe_cells"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recipe_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    breed_category: Mapped[str] = mapped_column(String(30), nullable=False)
    weight_min: Mapped[float] = mapped_column(Float, nullable=False)
    weight_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    labor_minutes: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)


class RecipeLineModel(Base):
    __tablename__ = "inventory_recipe_lines"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    cell_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_recipe_cells.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supply_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("inventory_supplies.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
