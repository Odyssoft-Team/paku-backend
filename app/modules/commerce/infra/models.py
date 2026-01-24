from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, JSON, Numeric, String
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ServiceModel(Base):
    __tablename__ = "services"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    species: Mapped[str] = mapped_column(String(20), nullable=False)

    allowed_breeds: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    requires: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class PriceRuleModel(Base):
    __tablename__ = "price_rules"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    service_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)

    species: Mapped[str] = mapped_column(String(20), nullable=False)
    breed_category: Mapped[str] = mapped_column(String(30), nullable=False)

    weight_min: Mapped[float] = mapped_column(Float, nullable=False)
    weight_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="PEN")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


_commerce_schema_ready = False


async def ensure_commerce_schema(engine: AsyncEngine) -> None:
    global _commerce_schema_ready
    if _commerce_schema_ready:
        return

    async with engine.begin() as conn:
        def _create(sync_conn):
            Base.metadata.create_all(
                sync_conn,
                tables=[ServiceModel.__table__, PriceRuleModel.__table__],
            )

        await conn.run_sync(_create)

    _commerce_schema_ready = True
