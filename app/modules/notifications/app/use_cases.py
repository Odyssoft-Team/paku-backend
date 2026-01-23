from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.notifications.domain.notification import Notification, NotificationRepository


@dataclass
class CreateNotification:
    repo: NotificationRepository

    async def execute(
        self,
        *,
        user_id: UUID,
        type: str,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
    ) -> Notification:
        return self.repo.create_notification(user_id=user_id, type=type, title=title, body=body, data=data)


@dataclass
class ListNotifications:
    repo: NotificationRepository

    async def execute(self, *, user_id: UUID, unread_only: bool = False, limit: int = 20) -> list[Notification]:
        return self.repo.list_notifications(user_id=user_id, unread_only=unread_only, limit=limit)


@dataclass
class MarkRead:
    repo: NotificationRepository

    async def execute(self, *, user_id: UUID, notification_id: UUID) -> Notification:
        try:
            return self.repo.mark_read(user_id=user_id, notification_id=notification_id)
        except ValueError as exc:
            if str(exc) == "notification_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found") from exc
            raise


@dataclass
class UnreadCount:
    repo: NotificationRepository

    async def execute(self, *, user_id: UUID) -> int:
        return self.repo.unread_count(user_id=user_id)
