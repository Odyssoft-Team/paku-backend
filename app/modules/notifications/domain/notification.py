from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Notification:
    id: UUID
    user_id: UUID
    type: str
    title: str
    body: str
    data: Optional[dict[str, Any]]
    is_read: bool
    created_at: datetime

    @staticmethod
    def new(
        *,
        user_id: UUID,
        type: str,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
        created_at: datetime,
    ) -> "Notification":
        return Notification(
            id=uuid4(),
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            data=data,
            is_read=False,
            created_at=created_at,
        )


class NotificationRepository(Protocol):
    def create_notification(
        self,
        user_id: UUID,
        type: str,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
    ) -> Notification:
        ...

    def list_notifications(self, user_id: UUID, *, unread_only: bool = False, limit: int = 20) -> list[Notification]:
        ...

    def mark_read(self, user_id: UUID, notification_id: UUID) -> Notification:
        ...

    def unread_count(self, user_id: UUID) -> int:
        ...
