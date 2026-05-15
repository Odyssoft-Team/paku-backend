from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.chat.api.schemas import MessageOut, SendMessageIn, UnreadCountOut
from app.modules.chat.app.use_cases import ListMessages, MarkReadForReceiver, SendMessage, UnreadCount
from app.modules.chat.infra.postgres_chat_repository import PostgresChatRepository
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository

router = APIRouter(tags=["chat"], prefix="/chat")

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Dependency helpers
# ------------------------------------------------------------------

def _get_chat_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresChatRepository:
    return PostgresChatRepository(session=session, engine=engine)


def _get_orders_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderRepository:
    return PostgresOrderRepository(session=session, engine=engine)


# ------------------------------------------------------------------
# Access guard
# Valida que el requester pertenezca a la orden (user dueño, ally asignado o admin).
# Devuelve la orden para que los endpoints puedan obtener ally_id / user_id.
# ------------------------------------------------------------------

async def _get_order_or_403(
    order_id: UUID,
    current: CurrentUser,
    orders_repo: PostgresOrderRepository,
):
    order = await orders_repo.get_order_admin(id=order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order_not_found")

    is_owner = order.user_id == current.id
    is_ally  = order.ally_id == current.id
    is_admin = current.role == "admin"

    if not (is_owner or is_ally or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="chat_forbidden")

    return order


# ------------------------------------------------------------------
# POST /chat/orders/{order_id}/messages
# Envía un mensaje en la conversación de una orden.
# ------------------------------------------------------------------
@router.post(
    "/orders/{order_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    order_id: UUID,
    body: SendMessageIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    chat_repo: PostgresChatRepository = Depends(_get_chat_repo),
    orders_repo: PostgresOrderRepository = Depends(_get_orders_repo),
) -> MessageOut:
    """
    Envía un mensaje de texto en el chat de una orden.

    Acceso: usuario dueño de la orden, ally asignado o admin.
    El mensaje queda persistido en PostgreSQL; el destinatario lo obtiene
    en su próxima petición de polling a GET /messages.
    """
    request_id = getattr(request.state, "request_id", None)

    order = await _get_order_or_403(order_id, current, orders_repo)

    # Determinar rol del sender y el id del destinatario para el push
    if current.role == "admin":
        sender_role = "admin"
        recipient_id = None
    elif order.user_id == current.id:
        sender_role = "user"
        recipient_id = order.ally_id  # puede ser None si aún no hay ally asignado
    else:
        sender_role = "ally"
        recipient_id = order.user_id

    logger.info(
        "chat.send_message order_id=%s sender_id=%s sender_role=%s request_id=%s",
        order_id, current.id, sender_role, request_id,
    )

    message = await SendMessage(repo=chat_repo).execute(
        order_id=order_id,
        sender_id=current.id,
        sender_role=sender_role,
        body=body.body,
        recipient_id=recipient_id,
    )

    return MessageOut(
        id=message.id,
        order_id=message.order_id,
        sender_id=message.sender_id,
        sender_role=message.sender_role,
        body=message.body,
        is_read=message.is_read,
        created_at=message.created_at,
    )


# ------------------------------------------------------------------
# GET /chat/orders/{order_id}/messages
# Polling: devuelve mensajes de la orden, opcionalmente a partir de un timestamp.
#
# Uso del cliente:
#   Primera carga  → GET /chat/orders/{id}/messages
#   Polling (cada 3s) → GET /chat/orders/{id}/messages?since=<created_at del último msg>
#
# Esto garantiza que el cliente nunca reciba el mismo mensaje dos veces y que
# cada petición devuelva solo el diferencial (normalmente 0–2 mensajes).
# ------------------------------------------------------------------
@router.get(
    "/orders/{order_id}/messages",
    response_model=list[MessageOut],
)
async def list_messages(
    order_id: UUID,
    since: Optional[datetime] = Query(
        default=None,
        description="Cursor ISO-8601. Devuelve solo mensajes posteriores a este timestamp.",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    chat_repo: PostgresChatRepository = Depends(_get_chat_repo),
    orders_repo: PostgresOrderRepository = Depends(_get_orders_repo),
) -> list[MessageOut]:
    """
    Devuelve los mensajes de chat de una orden.

    Para polling continuo, enviar `since` con el `created_at` del último
    mensaje recibido. La respuesta estará vacía cuando no haya mensajes nuevos.

    También marca como leídos los mensajes del otro participante.
    """
    await _get_order_or_403(order_id, current, orders_repo)

    messages = await ListMessages(repo=chat_repo).execute(
        order_id=order_id,
        since=since,
        limit=limit,
    )

    # Marcar leídos los mensajes dirigidos al llamante (best-effort)
    if messages:
        try:
            await MarkReadForReceiver(repo=chat_repo).execute(
                order_id=order_id,
                receiver_id=current.id,
            )
        except Exception:
            pass

    return [
        MessageOut(
            id=m.id,
            order_id=m.order_id,
            sender_id=m.sender_id,
            sender_role=m.sender_role,
            body=m.body,
            is_read=m.is_read,
            created_at=m.created_at,
        )
        for m in messages
    ]


# ------------------------------------------------------------------
# GET /chat/orders/{order_id}/unread-count
# Devuelve cuántos mensajes no leídos tiene el llamante en esta orden.
# Útil para mostrar badge en la UI sin traer el historial completo.
# ------------------------------------------------------------------
@router.get(
    "/orders/{order_id}/unread-count",
    response_model=UnreadCountOut,
)
async def unread_count(
    order_id: UUID,
    current: CurrentUser = Depends(get_current_user),
    chat_repo: PostgresChatRepository = Depends(_get_chat_repo),
    orders_repo: PostgresOrderRepository = Depends(_get_orders_repo),
) -> UnreadCountOut:
    """
    Devuelve el número de mensajes no leídos para el usuario actual en la orden.
    """
    await _get_order_or_403(order_id, current, orders_repo)

    count = await UnreadCount(repo=chat_repo).execute(
        order_id=order_id,
        receiver_id=current.id,
    )
    return UnreadCountOut(unread_count=count)
