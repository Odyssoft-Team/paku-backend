from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BreedModel(Base):
    __tablename__ = "breeds"

    # El id es el slug canónico, ej: "afghan_hound" — mismo valor que referencia commerce
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    species: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_breeds_species", "species"),
        Index("ix_breeds_species_active", "species", "is_active"),
    )
