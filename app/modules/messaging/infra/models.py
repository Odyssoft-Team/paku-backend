from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, Text
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
