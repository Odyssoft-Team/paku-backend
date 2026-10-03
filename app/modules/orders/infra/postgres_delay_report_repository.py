from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.domain.delay_report import DelayReport


class PostgresDelayReportRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: DelayReport) -> DelayReport:
        from app.modules.orders.infra.models import OrderDelayReportModel

        self._session.add(OrderDelayReportModel(
            id=report.id,
            order_id=report.order_id,
            groomer_id=report.groomer_id,
            delay_minutes=report.delay_minutes,
            note=report.note,
            created_at=report.created_at,
        ))
        await self._session.commit()
        return report

    async def list_by_order(self, order_id: UUID) -> list[DelayReport]:
        from app.modules.orders.infra.models import OrderDelayReportModel

        stmt = (
            select(OrderDelayReportModel)
            .where(OrderDelayReportModel.order_id == order_id)
            .order_by(OrderDelayReportModel.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            DelayReport(
                id=r.id, order_id=r.order_id, groomer_id=r.groomer_id, delay_minutes=r.delay_minutes,
                created_at=r.created_at, note=r.note,
            )
            for r in rows
        ]
