"""
Use case that resolves a StreamSession for a given order and requester.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

import logging
import jwt

from fastapi import HTTPException, status
from app.core.settings import settings
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.streaming.domain.session import StreamSession, resolve_stream_session

logger = logging.getLogger(__name__)


@dataclass
class GetStreamSession:
    orders_repo: PostgresOrderRepository

    async def execute(
        self,
        *,
        order_id: UUID,
        requester_id: UUID,
        requester_role: str,   # "user" | "ally" | "admin"
    ) -> tuple[StreamSession, str | None]:

        # Buscar la orden sin restricción de user_id para que admin y ally
        # también puedan consultarla.
        order = await self.orders_repo.get_order_admin(id=order_id)

        if order is None:
            logger.info("streaming.get_stream_session order_not_found order_id=%s requester_id=%s", order_id, requester_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="order_not_found",
            )

        logger.info("streaming.get_stream_session order_found order_id=%s status=%s ally_id=%s requester_id=%s requester_role=%s",
                    order_id, order.status.value, order.ally_id, requester_id, requester_role)

        # Delegar reglas de negocio puras a resolve_stream_session
        try:
            session = resolve_stream_session(
                order=order,
                requester_id=requester_id,
                requester_role=requester_role,
            )
        except ValueError as exc:
            # Resolver el error en detalle y mapear a HTTPException con códigos apropiados
            msg = str(exc)
            if msg.startswith("stream_not_available"):
                logger.warning("streaming.get_stream_session not_available order_id=%s status=%s requester_id=%s", order_id, order.status.value, requester_id)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg) from exc
            if msg.startswith("stream_forbidden") or msg.startswith("stream_forbidden"):
                logger.warning("streaming.get_stream_session forbidden order_id=%s requester_id=%s requester_role=%s", order_id, requester_id, requester_role)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
            logger.exception("streaming.get_stream_session unexpected_error order_id=%s requester_id=%s: %s", order_id, requester_id, exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="internal_error") from exc

        # Generación del JWT para el signaling server
        now = datetime.now(timezone.utc)

        token_payload = {
            "sub": str(requester_id),
            "role": session.role.value,
            "room": str(session.channel_id),
            "iss": "main-backend",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": str(uuid4()),
        }

        stream_token = jwt.encode(
            token_payload,
            settings.STREAMING_SECRET,
            algorithm="HS256",
        )

        logger.info("streaming.get_stream_session resolved order_id=%s channel_id=%s role=%s requester_id=%s", order_id, session.channel_id, session.role, requester_id)

        return session, stream_token