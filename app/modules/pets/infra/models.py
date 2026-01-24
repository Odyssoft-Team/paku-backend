from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PetModel(Base):
    __tablename__ = "pets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    species: Mapped[str] = mapped_column(String(20), nullable=False)
    breed: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class PetWeightEntryModel(Base):
    __tablename__ = "pet_weight_entries"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    pet_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


_pets_schema_ready = False


async def ensure_pets_schema(engine: AsyncEngine) -> None:
    global _pets_schema_ready
    if _pets_schema_ready:
        return

    async with engine.begin() as conn:
        def _create(sync_conn):
            Base.metadata.create_all(
                sync_conn,
                tables=[PetModel.__table__, PetWeightEntryModel.__table__],
            )

        await conn.run_sync(_create)

    _pets_schema_ready = True
