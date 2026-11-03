from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChannelProviderModel(Base):
    """Proveedor configurado para un canal de envío (feature 0018). Una fila por canal (`email`, luego `whatsapp`).

    La credencial se guarda cifrada (Fernet, `app/core/crypto.py`); `secret_mask` es lo único que ve el admin.
    """
    __tablename__ = "channel_providers"

    channel: Mapped[str] = mapped_column(String(20), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    secret_mask: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    from_email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    from_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reply_to: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_test_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class NotificationLogModel(Base):
    """Un envío por un canal (feature 0018 fase 2). `idempotency_key` único: el mismo envío no sale dos veces.

    `payload` guarda el mensaje armado (html, text, tags) para poder reintentarlo igual.
    """
    __tablename__ = "notification_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    recipient: Mapped[str] = mapped_column(String(254), nullable=False)
    template: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    order_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    campaign_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
