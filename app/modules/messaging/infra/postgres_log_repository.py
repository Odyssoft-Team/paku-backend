from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.domain.logs import FAILED, PENDING, STUCK_PENDING_MINUTES
from app.modules.messaging.infra.models import NotificationLogModel


class PostgresLogRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def get(self, log_id: UUID) -> Optional[NotificationLogModel]:
        return await self._session.get(NotificationLogModel, log_id)

    async def get_by_key(self, key: str) -> Optional[NotificationLogModel]:
        stmt = select(NotificationLogModel).where(NotificationLogModel.idempotency_key == key)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add(self, log: NotificationLogModel) -> tuple[NotificationLogModel, bool]:
        """Inserta; si otra petición ya registró la misma `idempotency_key`, devuelve esa (`created=False`)."""
        self._session.add(log)
        try:
            await self._session.commit()
            return log, True
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_by_key(log.idempotency_key)
            if existing is None:
                raise
            return existing, False

    async def save(self, log: NotificationLogModel) -> NotificationLogModel:
        self._session.add(log)
        await self._session.commit()
        return log

    async def due_retries(self, *, now: datetime, limit: int = 50) -> list[NotificationLogModel]:
        stuck_before = now - timedelta(minutes=STUCK_PENDING_MINUTES)
        stmt = (
            select(NotificationLogModel)
            .where(or_(
                (NotificationLogModel.status == FAILED) & NotificationLogModel.retryable
                & (NotificationLogModel.next_attempt_at <= now),
                (NotificationLogModel.status == PENDING) & (NotificationLogModel.updated_at <= stuck_before),
            ))
            .order_by(NotificationLogModel.created_at)
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    def _filtered(self, stmt, *, channel, status, q, created_from, created_to):
        if channel:
            stmt = stmt.where(NotificationLogModel.channel == channel)
        if status:
            stmt = stmt.where(NotificationLogModel.status == status)
        if created_from:
            stmt = stmt.where(NotificationLogModel.created_at >= created_from)
        if created_to:
            stmt = stmt.where(NotificationLogModel.created_at < created_to)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(or_(func.lower(NotificationLogModel.recipient).like(like),
                                  func.lower(NotificationLogModel.subject).like(like)))
        return stmt

    async def search(self, *, channel: Optional[str], status: Optional[str], q: Optional[str],
                     created_from: Optional[datetime], created_to: Optional[datetime], limit: int,
                     offset: int) -> tuple[list[NotificationLogModel], int, dict[str, int]]:
        """Página de envíos (más recientes primero), total con filtros y conteo por estado (sin filtrar estado)."""
        filters = dict(channel=channel, q=q, created_from=created_from, created_to=created_to)
        rows_stmt = self._filtered(select(NotificationLogModel), status=status, **filters)
        rows = (await self._session.execute(
            rows_stmt.order_by(NotificationLogModel.created_at.desc()).limit(limit).offset(offset)
        )).scalars().all()
        total_stmt = self._filtered(select(func.count()).select_from(NotificationLogModel), status=status, **filters)
        total = (await self._session.execute(total_stmt)).scalar_one()
        counts_stmt = self._filtered(
            select(NotificationLogModel.status, func.count()).group_by(NotificationLogModel.status),
            status=None, **filters,
        )
        counts = {s: n for s, n in (await self._session.execute(counts_stmt)).all()}
        return list(rows), total, counts
