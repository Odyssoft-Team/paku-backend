from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.chat.domain.message import Message, MessageRepository


class PostgresChatRepository(MessageRepository):
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_message(row) -> Message:
        return Message(
            id=row.id,
            order_id=row.order_id,
            sender_id=row.sender_id,
            sender_role=row.sender_role,
            body=row.body,
            is_read=row.is_read,
            created_at=row.created_at,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save(self, message: Message) -> Message:
        from app.modules.chat.infra.models import ChatMessageModel

        model = ChatMessageModel(
            id=message.id,
            order_id=message.order_id,
            sender_id=message.sender_id,
            sender_role=message.sender_role,
            body=message.body,
            is_read=message.is_read,
            created_at=message.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return message

    async def mark_read_for_receiver(
        self,
        order_id: UUID,
        receiver_id: UUID,
    ) -> None:
        """Marca como leídos todos los mensajes de la orden que NO fueron enviados
        por receiver_id (es decir, los mensajes dirigidos a él)."""
        from app.modules.chat.infra.models import ChatMessageModel

        stmt = (
            update(ChatMessageModel)
            .where(
                ChatMessageModel.order_id == order_id,
                ChatMessageModel.sender_id != receiver_id,
                ChatMessageModel.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_since(
        self,
        order_id: UUID,
        *,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[Message]:
        """Devuelve mensajes de una orden, opcionalmente filtrados a partir de
        un timestamp (cursor-based polling: el cliente envía el created_at del
        último mensaje que ya tiene)."""
        from app.modules.chat.infra.models import ChatMessageModel

        stmt = select(ChatMessageModel).where(ChatMessageModel.order_id == order_id)

        if since is not None:
            stmt = stmt.where(ChatMessageModel.created_at > since)

        stmt = stmt.order_by(ChatMessageModel.created_at.asc()).limit(limit)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._row_to_message(r) for r in rows]

    async def unread_count(self, order_id: UUID, receiver_id: UUID) -> int:
        """Cuenta mensajes no leídos dirigidos a receiver_id en la orden."""
        from app.modules.chat.infra.models import ChatMessageModel

        stmt = select(func.count()).where(
            ChatMessageModel.order_id == order_id,
            ChatMessageModel.sender_id != receiver_id,
            ChatMessageModel.is_read.is_(False),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
