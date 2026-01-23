from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.modules.notifications.domain.notification import Notification, NotificationRepository


class InMemoryNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self._by_id: Dict[UUID, Notification] = {}
        self._by_user: Dict[UUID, List[UUID]] = {}

    def create_notification(
        self,
        user_id: UUID,
        type: str,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
    ) -> Notification:
        now = datetime.now(timezone.utc)
        n = Notification.new(user_id=user_id, type=type, title=title, body=body, data=data, created_at=now)
        self._by_id[n.id] = n
        if user_id not in self._by_user:
            self._by_user[user_id] = []
        self._by_user[user_id].append(n.id)
        return n

    def list_notifications(self, user_id: UUID, *, unread_only: bool = False, limit: int = 20) -> list[Notification]:
        ids = self._by_user.get(user_id, [])
        items: List[Notification] = []
        for nid in ids:
            n = self._by_id.get(nid)
            if n is None:
                continue
            if unread_only and n.is_read:
                continue
            items.append(n)

        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[: max(0, int(limit))]

    def mark_read(self, user_id: UUID, notification_id: UUID) -> Notification:
        n = self._by_id.get(notification_id)
        if not n or n.user_id != user_id:
            raise ValueError("notification_not_found")

        if n.is_read:
            return n

        updated = Notification(
            id=n.id,
            user_id=n.user_id,
            type=n.type,
            title=n.title,
            body=n.body,
            data=n.data,
            is_read=True,
            created_at=n.created_at,
        )
        self._by_id[notification_id] = updated
        return updated

    def unread_count(self, user_id: UUID) -> int:
        ids = self._by_user.get(user_id, [])
        count = 0
        for nid in ids:
            n = self._by_id.get(nid)
            if n is None:
                continue
            if not n.is_read:
                count += 1
        return count
