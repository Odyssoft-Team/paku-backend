from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# [TECH]
# SQLAlchemy ORM model for chat_messages table.
# order_id is not a FK to avoid coupling to the orders module at DB level;
# referential integrity is enforced at the application layer (use cases).
#
# [NATURAL/BUSINESS]
# Tabla de mensajes de chat. Cada fila es un mensaje enviado dentro de una orden.
class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    sender_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "ally"
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )

    __table_args__ = (
        # Query principal: mensajes de una orden ordenados por tiempo
        Index("ix_chat_messages_order_created", "order_id", "created_at"),
        # Para marcar leídos: mensajes no leídos recibidos por alguien
        Index("ix_chat_messages_order_unread", "order_id", "is_read"),
    )


async def ensure_chat_schema(engine: AsyncEngine) -> None:
    # DDL gestionado por Alembic. No crear tablas aquí.
    pass
