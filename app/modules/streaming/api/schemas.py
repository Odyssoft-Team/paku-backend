from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.orders.domain.order import OrderStatus
from app.modules.streaming.domain.session import StreamRole


# [TECH]
# ICE server configuration returned to the mobile client.
# Mirrors the RTCIceServer interface expected by react-native-webrtc.
# In production, `username` and `credential` should be generated dynamically
# by the TURN server. For now they are static (see settings).
#
# [STREAMING DEV]
# When you implement dynamic TURN credential generation, replace the static
# values in StreamingSettings with your generation logic and populate this
# object accordingly.
class IceServerOut(BaseModel):
    urls: list[str]
    username: Optional[str] = None
    credential: Optional[str] = None


# [TECH]
# Response schema returned to both mobile clients (ally and user)
# after a successful GET /streaming/orders/{order_id}/session call.
# Contains everything the app needs to open the WebSocket and start WebRTC —
# no additional calls required.
#
# [BUSINESS]
# Con una sola llamada autenticada, la app obtiene:
#   - room_id     → cadena que ambas partes usan como ?room= en el WebSocket
#   - ws_url      → URL completa lista para conectar (incluye room_id)
#   - role        → "host" (ally) o "viewer" (cliente/admin)
#   - ice_servers → configuración ICE/TURN lista para RTCPeerConnection
#
# [STREAMING DEV]
# `room_id` == order_id as string. Use it as the `room` query param:
#   wss://stream.dev-qa.site/ws?room={room_id}
# `ws_url` already has it assembled for convenience.
# `ice_servers` maps 1:1 to the RTCPeerConnection iceServers array.
# When you add dynamic TURN credentials, populate `username` and `credential`
# in the IceServerOut for the TURN entry.
class StreamSessionOut(BaseModel):
    # Identifiers
    room_id: str            # == str(order_id) — the ?room= param for the WebSocket
    order_id: UUID
    user_id: UUID           # cliente dueño de la orden
    ally_id: UUID           # ally asignado (broadcaster / host)
    order_status: OrderStatus
    role: StreamRole        # "host" | "viewer"

    # Connection info — ready to use, no extra calls needed
    ws_url: str             # full WebSocket URL: wss://.../ws?room={room_id}
    ice_servers: list[IceServerOut]  # drop this into RTCPeerConnection({ iceServers })

    model_config = {"use_enum_values": True}
