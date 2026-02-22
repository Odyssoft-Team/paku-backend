from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.notifications.domain.notification import Notification, NotificationRepository


class PostgresNotificationRepository(NotificationRepository):
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def create_notification(
        self,
        user_id: UUID,
        type: str,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
    ) -> Notification:
        now = datetime.now(timezone.utc)
        notification = Notification.new(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            data=data,
            created_at=now,
        )

        from app.modules.notifications.infra.models import NotificationModel

        model = NotificationModel(
            id=notification.id,
            user_id=notification.user_id,
            type=notification.type,
            title=notification.title,
            body=notification.body,
            data=notification.data,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return notification

    async def list_notifications(self, user_id: UUID, *, unread_only: bool = False, limit: int = 20) -> list[Notification]:
        from app.modules.notifications.infra.models import NotificationModel

        stmt = select(NotificationModel).where(NotificationModel.user_id == user_id)
        if unread_only:
            stmt = stmt.where(NotificationModel.is_read.is_(False))
        stmt = stmt.order_by(NotificationModel.created_at.desc()).limit(limit)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            Notification(
                id=row.id,
                user_id=row.user_id,
                type=row.type,
                title=row.title,
                body=row.body,
                data=row.data,
                is_read=row.is_read,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def mark_read(self, user_id: UUID, notification_id: UUID) -> Notification:
        from app.modules.notifications.infra.models import NotificationModel

        stmt = (
            update(NotificationModel)
            .where(NotificationModel.id == notification_id, NotificationModel.user_id == user_id)
            .values(is_read=True)
            .returning(NotificationModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            raise ValueError("notification_not_found")

        return Notification(
            id=row.id,
            user_id=row.user_id,
            type=row.type,
            title=row.title,
            body=row.body,
            data=row.data,
            is_read=row.is_read,
            created_at=row.created_at,
        )

    async def unread_count(self, user_id: UUID) -> int:
        from app.modules.notifications.infra.models import NotificationModel

        stmt = select(NotificationModel).where(
            NotificationModel.user_id == user_id, NotificationModel.is_read.is_(False)
        )
        result = await self._session.execute(stmt)
        return len(result.scalars().all())
