from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID, uuid4


# [TECH]
# Immutable entity representing a single chat message within an order conversation.
#
# [NATURAL/BUSINESS]
# Mensaje de texto enviado entre el cliente y el ally durante una orden activa.
# El canal de chat está siempre asociado a una orden; no existe chat fuera de una orden.
@dataclass(frozen=True)
class Message:
    id: UUID
    order_id: UUID
    sender_id: UUID
    sender_role: str          # "user" | "ally"
    body: str
    created_at: datetime
    is_read: bool

    # [TECH]
    # Factory creating a new unread Message with a generated UUID and given timestamp.
    #
    # [NATURAL/BUSINESS]
    # Crea un mensaje nuevo aún no leído por el destinatario.
    @staticmethod
    def new(
        *,
        order_id: UUID,
        sender_id: UUID,
        sender_role: str,
        body: str,
        created_at: datetime,
    ) -> "Message":
        return Message(
            id=uuid4(),
            order_id=order_id,
            sender_id=sender_id,
            sender_role=sender_role,
            body=body,
            created_at=created_at,
            is_read=False,
        )


# [TECH]
# Repository interface for chat message persistence.
# Concrete implementation lives in infra/postgres_chat_repository.py.
#
# [NATURAL/BUSINESS]
# Guarda y consulta mensajes de chat asociados a una orden.
class MessageRepository(Protocol):
    async def save(self, message: Message) -> Message:
        ...

    async def list_since(
        self,
        order_id: UUID,
        *,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[Message]:
        ...

    async def mark_read_for_receiver(
        self,
        order_id: UUID,
        receiver_id: UUID,
    ) -> None:
        ...

    async def unread_count(self, order_id: UUID, receiver_id: UUID) -> int:
        ...
