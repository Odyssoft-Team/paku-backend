from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WalletCardModel(Base):
    __tablename__ = "wallet_cards"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # Token / ID genérico del método de pago (legado; se mantiene por compatibilidad)
    payment_method_id: Mapped[str] = mapped_column(String(100), nullable=False)
    brand: Mapped[str] = mapped_column(String(30), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    exp_month: Mapped[int] = mapped_column(nullable=False)
    exp_year: Mapped[int] = mapped_column(nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # IDs de Culqi para cargos One-click — presentes solo cuando se registró vía Culqi
    culqi_customer_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    culqi_card_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


async def ensure_wallet_schema(engine: AsyncEngine) -> None:
    # DDL gestionado por Alembic. No crear tablas aquí.
    pass
