from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

import logging

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.core.settings import settings
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.streaming.api.schemas import IceServerOut, StreamSessionOut
from app.modules.streaming.use_cases.get_stream_session import GetStreamSession

router = APIRouter(tags=["streaming"], prefix="/streaming")

logger = logging.getLogger(__name__)


def _get_orders_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderRepository:
    return PostgresOrderRepository(session=session, engine=engine)


def _build_ice_servers() -> list[IceServerOut]:
    """
    Construye la lista de ICE servers lista para RTCPeerConnection({ iceServers }).
    Los valores vienen de settings para que sean cambiables por variable de entorno
    sin tocar código.

    STREAMING DEV: cuando implementes credenciales TURN dinámicas, reemplaza
    esta función por la lógica de generación y devuelve los mismos objetos IceServerOut.
    """
    return [
        IceServerOut(urls=[settings.STREAMING_STUN_URL]),
        IceServerOut(
            urls=settings.STREAMING_TURN_URLS.split(","),
            username=settings.STREAMING_TURN_USERNAME,
            credential=settings.STREAMING_TURN_CREDENTIAL,
        ),
    ]


# ------------------------------------------------------------------
# GET /streaming/orders/{order_id}/session
# ------------------------------------------------------------------
# Disponible para: ally asignado, cliente dueño de la orden, admin.
#
# La app llama a este endpoint ANTES de conectarse al WebSocket de señalización.
# La respuesta incluye todo lo necesario para iniciar WebRTC sin ninguna llamada adicional:
#   - ws_url      → conectar directamente: new WebSocket(ws_url)
#   - room_id     → el ?room= param (= order_id como string)
#   - ice_servers → pasar directo a RTCPeerConnection({ iceServers: ice_servers })
#   - role        → "host" si es el ally (genera offer), "viewer" si es el cliente (espera)
#
# Solo disponible cuando order_status == in_service.
# ------------------------------------------------------------------
@router.get("/orders/{order_id}/session", response_model=StreamSessionOut)
async def get_stream_session(
    order_id: UUID,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    orders_repo: PostgresOrderRepository = Depends(_get_orders_repo),
) -> StreamSessionOut:
    """
    Resuelve la sesión de streaming para una orden activa.
    """
    # Información de correlación
    request_id = getattr(request.state, "request_id", None)
    client_ip = request.client.host if request and request.client else None

    logger.info(
        "streaming.request_session received order_id=%s requester_id=%s requester_role=%s request_id=%s client_ip=%s",
        order_id, current.id, current.role, request_id, client_ip,
    )

    try:
        session, stream_token = await GetStreamSession(orders_repo=orders_repo).execute(
            order_id=order_id,
            requester_id=current.id,
            requester_role=current.role,
        )
    except Exception as exc:
        # Log la excepción con correlación y re-raise para que FastAPI la gestione
        logger.exception(
            "streaming.request_session failed order_id=%s requester_id=%s request_id=%s: %s",
            order_id, current.id, request_id, exc,
        )
        raise

    room_id = str(session.channel_id)
    ws_url = f"{settings.STREAMING_SIGNALING_URL}?room={room_id}"

    logger.info(
        "streaming.session_resolved order_id=%s channel_id=%s role=%s stream_token_present=%s request_id=%s",
        order_id, session.channel_id, session.role, bool(stream_token), request_id,
    )

    return StreamSessionOut(
        room_id=room_id,
        order_id=session.order_id,
        user_id=session.user_id,
        ally_id=session.ally_id,
        order_status=session.order_status,
        role=session.role,
        ws_url=ws_url,
        stream_token=stream_token,
        ice_servers=_build_ice_servers(),
    )
