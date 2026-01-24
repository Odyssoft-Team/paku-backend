from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.notifications.api.schemas import NotificationOut, UnreadCountOut
from app.modules.notifications.app.use_cases import ListNotifications, MarkRead, UnreadCount
from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository


router = APIRouter(tags=["notifications"], prefix="/notifications")


def get_notifications_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresNotificationRepository:
    return PostgresNotificationRepository(session=session, engine=engine)


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresNotificationRepository = Depends(get_notifications_repo),
) -> list[NotificationOut]:
    items = await ListNotifications(repo=repo).execute(user_id=current.id, unread_only=unread_only, limit=limit)
    return [NotificationOut(**n.__dict__) for n in items]


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresNotificationRepository = Depends(get_notifications_repo),
) -> UnreadCountOut:
    count = await UnreadCount(repo=repo).execute(user_id=current.id)
    return UnreadCountOut(unread_count=count)


@router.post("/{id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresNotificationRepository = Depends(get_notifications_repo),
) -> None:
    await MarkRead(repo=repo).execute(user_id=current.id, notification_id=id)
    return None
