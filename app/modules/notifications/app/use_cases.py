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
        n = await self.repo.create_notification(user_id=user_id, type=type, title=title, body=body, data=data)

        # Push al teléfono (best-effort). `type` va en data para que la app elija ícono y navegación.
        from app.modules.push.app.use_cases import send_push_to_user

        await send_push_to_user(user_id, title=title, body=body, data={**(data or {}), "type": type})
        return n


@dataclass
class ListNotifications:
    repo: NotificationRepository

    async def execute(self, *, user_id: UUID, unread_only: bool = False, limit: int = 20) -> list[Notification]:
        return await self.repo.list_notifications(user_id=user_id, unread_only=unread_only, limit=limit)


@dataclass
class MarkRead:
    repo: NotificationRepository

    async def execute(self, *, user_id: UUID, notification_id: UUID) -> Notification:
        try:
            return await self.repo.mark_read(user_id=user_id, notification_id=notification_id)
        except ValueError as exc:
            if str(exc) == "notification_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found") from exc
            raise


@dataclass
class UnreadCount:
    repo: NotificationRepository

    async def execute(self, *, user_id: UUID) -> int:
        return await self.repo.unread_count(user_id=user_id)
