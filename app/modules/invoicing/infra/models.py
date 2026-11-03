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


class InvoicingProviderModel(Base):
    """Proveedor de facturación electrónica (feature 0020). Una fila por proveedor (`nubefact`).

    El token se guarda cifrado (Fernet, `app/core/crypto.py`); `token_mask` es lo único que ve el admin.
    """
    __tablename__ = "invoicing_providers"

    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    api_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_mask: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    boleta_series: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_test_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
