from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, Numeric, String
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

    status: Mapped[str] = mapped_column(String(30), nullable=False)

    items_snapshot: Mapped[Any] = mapped_column(JSON, nullable=False)
    total_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="PEN")
    delivery_address_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


_orders_schema_ready = False


async def ensure_orders_schema(engine: AsyncEngine) -> None:
    global _orders_schema_ready
    if _orders_schema_ready:
        return

    async with engine.begin() as conn:
        def _create(sync_conn):
            Base.metadata.create_all(sync_conn, tables=[OrderModel.__table__])

        await conn.run_sync(_create)

    _orders_schema_ready = True
