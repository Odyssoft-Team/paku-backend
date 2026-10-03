from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.domain.photo import OrderPhoto, OrderPhotoKind


class PostgresOrderPhotoRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _row_to_photo(r) -> OrderPhoto:
        return OrderPhoto(
            id=r.id,
            order_id=r.order_id,
            kind=OrderPhotoKind(r.kind),
            object_name=r.object_name,
            uploaded_by=r.uploaded_by,
            created_at=r.created_at,
            note=r.note,
        )

    async def add(self, photo: OrderPhoto) -> OrderPhoto:
        from app.modules.orders.infra.models import OrderPhotoModel

        self._session.add(OrderPhotoModel(
            id=photo.id,
            order_id=photo.order_id,
            kind=photo.kind.value,
            object_name=photo.object_name,
            note=photo.note,
            uploaded_by=photo.uploaded_by,
            created_at=photo.created_at,
        ))
        await self._session.commit()
        return photo

    async def list_by_order(self, order_id: UUID) -> list[OrderPhoto]:
        from app.modules.orders.infra.models import OrderPhotoModel

        stmt = (
            select(OrderPhotoModel)
            .where(OrderPhotoModel.order_id == order_id)
            .order_by(OrderPhotoModel.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_photo(r) for r in rows]

    async def has_kind(self, order_id: UUID, kind: OrderPhotoKind) -> bool:
        from app.modules.orders.infra.models import OrderPhotoModel

        stmt = (
            select(OrderPhotoModel.id)
            .where(OrderPhotoModel.order_id == order_id, OrderPhotoModel.kind == kind.value)
            .limit(1)
        )
        return (await self._session.execute(stmt)).first() is not None
