from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, String
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sex: Mapped[str] = mapped_column(String(10), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)

    dni: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    address_district_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address_line: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    address_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    profile_photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


_iam_schema_ready = False


async def ensure_iam_schema(engine: AsyncEngine) -> None:
    global _iam_schema_ready
    if _iam_schema_ready:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _iam_schema_ready = True
