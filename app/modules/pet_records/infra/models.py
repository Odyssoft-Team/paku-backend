from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PetRecordModel(Base):
    __tablename__ = "pet_records"
    __table_args__ = (
        Index("ix_pet_records_pet_id_type", "pet_id", "type"),
        Index("ix_pet_records_pet_id_occurred_at", "pet_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    pet_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    recorded_by_user_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    recorded_by_role: Mapped[str] = mapped_column(String(20), nullable=False)

    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    attachment_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
