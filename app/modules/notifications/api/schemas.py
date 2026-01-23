from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


# [TECH]
# Output DTO serializing Notification for API responses.
#
# [NATURAL/BUSINESS]
# Representación de notificación que devuelve la API.
class NotificationOut(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    title: str
    body: str
    data: Optional[dict[str, Any]] = None
    is_read: bool
    created_at: datetime


# [TECH]
# Output DTO for unread notification count.
#
# [NATURAL/BUSINESS]
# Cantidad de notificaciones no leídas del usuario.
class UnreadCountOut(BaseModel):
    unread_count: int
