from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# [TECH]
# Input DTO for sending a new chat message.
#
# [NATURAL/BUSINESS]
# Cuerpo del mensaje que el cliente o ally envía en la conversación de una orden.
class SendMessageIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


# [TECH]
# Output DTO serializing a Message for API responses.
#
# [NATURAL/BUSINESS]
# Representación de un mensaje de chat que devuelve la API.
class MessageOut(BaseModel):
    id: UUID
    order_id: UUID
    sender_id: UUID
    sender_role: str
    body: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# [TECH]
# Output DTO for unread message count.
#
# [NATURAL/BUSINESS]
# Cantidad de mensajes no leídos para el usuario actual en una orden.
class UnreadCountOut(BaseModel):
    unread_count: int
