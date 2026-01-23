from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.notifications.api.schemas import NotificationOut, UnreadCountOut
from app.modules.notifications.app.use_cases import ListNotifications, MarkRead, UnreadCount
from app.modules.notifications.infra.notification_repository import InMemoryNotificationRepository


router = APIRouter(tags=["notifications"], prefix="/notifications")
_repo = InMemoryNotificationRepository()


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
) -> list[NotificationOut]:
    items = await ListNotifications(repo=_repo).execute(user_id=current.id, unread_only=unread_only, limit=limit)
    return [NotificationOut(**n.__dict__) for n in items]


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(current: CurrentUser = Depends(get_current_user)) -> UnreadCountOut:
    count = await UnreadCount(repo=_repo).execute(user_id=current.id)
    return UnreadCountOut(unread_count=count)


@router.post("/{id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(id: UUID, current: CurrentUser = Depends(get_current_user)) -> None:
    await MarkRead(repo=_repo).execute(user_id=current.id, notification_id=id)
    return None
