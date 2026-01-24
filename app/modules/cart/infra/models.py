from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, Index, Integer, Numeric, String, Uuid
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.modules.cart.domain.cart import CartItemKind, CartStatus


class Base(DeclarativeBase):
    pass


class CartSessionModel(Base):
    __tablename__ = "cart_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=lambda: UUID())
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    status: Mapped[CartStatus] = mapped_column(Enum(CartStatus), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_cart_sessions_user_status", "user_id", "status"),
        Index("ix_cart_sessions_expires", "expires_at"),
    )


class CartItemModel(Base):
    __tablename__ = "cart_items"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=lambda: UUID())
    cart_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    kind: Mapped[CartItemKind] = mapped_column(Enum(CartItemKind), nullable=False)
    ref_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_cart_items_cart_id", "cart_id"),
        Index("ix_cart_items_kind_ref", "kind", "ref_id"),
    )


async def ensure_cart_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[CartSessionModel.__table__, CartItemModel.__table__])
