from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Index, String, Uuid
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.modules.push.domain.push import Platform


class Base(DeclarativeBase):
    pass


class DeviceTokenModel(Base):
    __tablename__ = "device_tokens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=lambda: UUID())
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    token: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_device_tokens_user_platform_token", "user_id", "platform", "token", unique=True),
        Index("ix_device_tokens_user_active", "user_id", "is_active"),
    )


async def ensure_push_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[DeviceTokenModel.__table__])
