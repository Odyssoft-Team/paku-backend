from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.modules.orders.domain.order import Order, OrderStatus


# [TECH]
# Enum representing the role a participant has inside a streaming channel.
# Used to communicate to the media server who is broadcasting vs. who is watching.
#
# [BUSINESS]
# El groomer es el HOST: el que inicia y transmite el video.
# El cliente es el VIEWER: solo puede ver la transmisión.
# El admin puede unirse como VIEWER para supervisión.
class StreamRole(str, Enum):
    host   = "host"    # groomer: abre el canal y transmite
    viewer = "viewer"  # cliente / admin: se une y visualiza


# [TECH]
# Value object representing a resolved streaming session.
# Not persisted — built on demand from an existing Order.
# Contains everything the media server needs to create or join a channel.
#
# [BUSINESS]
# Representa una sesión de transmisión en vivo asociada a una orden activa.
# El channel_id es directamente el UUID de la orden para evitar cualquier
# coordinación extra: ambas partes ya conocen ese ID.
@dataclass(frozen=True)
class StreamSession:
    channel_id: UUID        # == order.id  — identificador del canal en el media server
    order_id: UUID          # redundante pero explícito para claridad del consumidor
    user_id: UUID           # cliente dueño de la orden
    groomer_id: UUID           # groomer asignado (host)
    order_status: OrderStatus
    role: StreamRole        # rol del solicitante en este canal


# [TECH]
# Pure domain function that validates whether a streaming session can be
# resolved for a given requester, and builds the StreamSession value object.
# Raises ValueError with a descriptive code on any violation.
# No I/O — all inputs must be resolved before calling this.
#
# [BUSINESS]
# Reglas para habilitar una sesión de transmisión:
# 1. La orden debe estar en estado in_service.
# 2. La orden debe tener un groomer asignado.
# 3. Solo el cliente dueño de la orden, el groomer asignado o un admin pueden acceder.
# 4. El groomer obtiene rol HOST; el cliente y el admin obtienen rol VIEWER.
def resolve_stream_session(
    *,
    order: Order,
    requester_id: UUID,
    requester_role: str,   # "user" | "groomer" | "admin"  — viene del JWT
) -> StreamSession:

    # Regla 1 — solo cuando el servicio está en curso
    if order.status != OrderStatus.in_service:
        raise ValueError("stream_not_available: order is not in_service")

    # Regla 2 — debe haber un groomer asignado
    if order.groomer_id is None:
        raise ValueError("stream_not_available: order has no groomer assigned")

    # Regla 3 — solo participantes autorizados
    is_owner = requester_id == order.user_id
    is_groomer  = requester_id == order.groomer_id
    is_admin = requester_role == "admin"

    if not (is_owner or is_groomer or is_admin):
        raise ValueError("stream_forbidden: requester is not a participant of this order")

    # Regla 4 — asignación de rol
    role = StreamRole.host if is_groomer else StreamRole.viewer

    return StreamSession(
        channel_id=order.id,
        order_id=order.id,
        user_id=order.user_id,
        groomer_id=order.groomer_id,
        order_status=order.status,
        role=role,
    )
