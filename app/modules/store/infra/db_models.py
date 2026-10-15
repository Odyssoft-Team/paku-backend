from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, JSON, Numeric, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CategoryModel(Base):
    __tablename__ = "store_categories"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    species: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ProductModel(Base):
    __tablename__ = "store_products"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    category_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("store_categories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    species: Mapped[str] = mapped_column(String(20), nullable=False)
    allowed_breeds: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    included_items: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    max_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Código del documento de precios (Clásico, Medicado, Premium, Seco): lo usan las reglas (0008)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AddonModel(Base):
    __tablename__ = "store_addons"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("store_products.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Catálogo de adicionales (hoja 18, feature 0008)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    requires_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_extra_min: Mapped[int | None] = mapped_column(Integer, nullable=True)  # pendiente del negocio
    species: Mapped[str] = mapped_column(String(20), nullable=False)
    allowed_breeds: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class StorePriceRuleModel(Base):
    __tablename__ = "store_price_rules"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "product" | "addon"
    species: Mapped[str] = mapped_column(String(20), nullable=False)
    breed_category: Mapped[str] = mapped_column(String(30), nullable=False)
    weight_min: Mapped[float] = mapped_column(Float, nullable=False)
    weight_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="PEN")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("ix_store_price_rules_lookup", "target_id", "target_type", "species", "breed_category"),
    )


class RecommendationRuleModel(Base):
    """Reglas del motor de recomendaciones (hojas 17 y 19, feature 0008). Se editan en la BD."""
    __tablename__ = "recommendation_rules"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)          # REC-001, AR-010…
    kind: Mapped[str] = mapped_column(String(10), nullable=False)          # service | addon
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    target_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requires_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
