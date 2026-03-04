from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from app.core.settings import settings
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.streaming.domain.session import StreamSession, resolve_stream_session


# [TECH]
# Use case that resolves a StreamSession for a given order and requester.
# Depends on PostgresOrderRepository (read-only) to fetch the order.
# All business rule validation is delegated to the domain function resolve_stream_session.
# Raises HTTP 404 / 403 / 409 as appropriate so the router stays thin.
#
# [BUSINESS]
# Verifica que la orden exista, que esté en in_service, y que el solicitante
# sea el cliente, el ally asignado o un admin. Devuelve la sesión con el
# channel_id y el rol que corresponde a ese participante.
#
# NOTE FOR THE STREAMING DEV:
# This is the single entry point your module needs to call before creating
# or joining a channel on the media server. It gives you:
#   - channel_id  → use this as the room/channel identifier on the media server
#   - role        → "host" means the ally (broadcaster), "viewer" means the client
#   - user_id / ally_id → available if your server needs participant metadata
@dataclass
class GetStreamSession:
    orders_repo: PostgresOrderRepository

    async def execute(
        self,
        *,
        order_id: UUID,
        requester_id: UUID,
        requester_role: str,   # "user" | "ally" | "admin"  — extraído del JWT
    ) -> tuple[StreamSession, str]:

        # Buscar la orden sin restricción de user_id para que admin y ally
        # también puedan consultarla.
        order = await self.orders_repo.get_order_admin(id=order_id)

        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="order_not_found",
            )

        try:
            session = resolve_stream_session(
                order=order,
                requester_id=requester_id,
                requester_role=requester_role,
            )
        except ValueError as exc:
            code = str(exc)
            if code.startswith("stream_forbidden"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not a participant of this order",
                )
            # stream_not_available — orden no está en in_service o sin ally
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )

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

        return session, stream_token