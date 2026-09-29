from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
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

    __table_args__ = (
        Index(
            "uq_wallet_cards_provider_culqi_card_id",
            "provider",
            "culqi_card_id",
            unique=True,
            postgresql_where=text("culqi_card_id IS NOT NULL"),
        ),
    )


class UserPaymentCustomerModel(Base):
    __tablename__ = "user_payment_customers"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="provisioning")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "(status = 'provisioning' AND customer_id IS NULL) "
            "OR (status = 'ready' AND customer_id IS NOT NULL)",
            name="ck_user_payment_customers_status_customer_id",
        ),
        UniqueConstraint("user_id", "provider", name="uq_user_payment_customers_user_provider"),
    )


async def ensure_wallet_schema(engine: AsyncEngine) -> None:
    # DDL gestionado por Alembic. No crear tablas aquí.
    pass
