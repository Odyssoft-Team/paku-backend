from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.chat.domain.message import Message, MessageRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------
# SendMessage
# ------------------------------------------------------------------

@dataclass
class SendMessage:
    repo: MessageRepository

    async def execute(
        self,
        *,
        order_id: UUID,
        sender_id: UUID,
        sender_role: str,
        body: str,
        # La orden ya fue validada en el router (acceso + estado in_service).
        # Se recibe ally_id y user_id para disparar push al destinatario.
        recipient_id: Optional[UUID] = None,
    ) -> Message:
        body = body.strip()
        if not body:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El mensaje no puede estar vacío.",
            )
        if len(body) > 2000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El mensaje no puede superar los 2000 caracteres.",
            )

        message = Message.new(
            order_id=order_id,
            sender_id=sender_id,
            sender_role=sender_role,
            body=body,
            created_at=_utcnow(),
        )
        saved = await self.repo.save(message)

        # Notificar al destinatario vía push (best-effort, no bloquea la respuesta)
        if recipient_id is not None:
            try:
                from app.core.db import engine, get_async_session
                from app.core.settings import settings
                from app.modules.push.domain.push import PushMessage
                from app.modules.push.infra.postgres_device_repository import PostgresDeviceTokenRepository
                from app.modules.push.infra.provider import ExpoPushProvider, MockPushProvider

                sender_label = "Tu groomer" if sender_role == "ally" else "Tu cliente"
                async with get_async_session() as session:
                    devices_repo = PostgresDeviceTokenRepository(session=session, engine=engine)
                    tokens = await devices_repo.get_active_tokens(recipient_id)
                    if tokens:
                        provider = ExpoPushProvider() if settings.ENV == "production" else MockPushProvider()
                        provider.send(
                            tokens=tokens,
                            message=PushMessage(
                                title=f"Mensaje de {sender_label}",
                                body=body[:100],
                                data={"order_id": str(order_id), "type": "chat_message"},
                            ),
                        )
            except Exception:
                pass  # El push es best-effort; nunca falla el endpoint

        return saved


# ------------------------------------------------------------------
# ListMessages
# ------------------------------------------------------------------

@dataclass
class ListMessages:
    repo: MessageRepository

    async def execute(
        self,
        *,
        order_id: UUID,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[Message]:
        return await self.repo.list_since(order_id=order_id, since=since, limit=limit)


# ------------------------------------------------------------------
# MarkReadForReceiver
# ------------------------------------------------------------------

@dataclass
class MarkReadForReceiver:
    repo: MessageRepository

    async def execute(self, *, order_id: UUID, receiver_id: UUID) -> None:
        await self.repo.mark_read_for_receiver(order_id=order_id, receiver_id=receiver_id)


# ------------------------------------------------------------------
# UnreadCount
# ------------------------------------------------------------------

@dataclass
class UnreadCount:
    repo: MessageRepository

    async def execute(self, *, order_id: UUID, receiver_id: UUID) -> int:
        return await self.repo.unread_count(order_id=order_id, receiver_id=receiver_id)
