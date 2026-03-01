from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.orders.domain.assignment import OrderAssignment


class PostgresOrderAssignmentRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    @staticmethod
    def _row_to_domain(r) -> OrderAssignment:
        return OrderAssignment(
            id=r.id,
            order_id=r.order_id,
            ally_id=r.ally_id,
            scheduled_at=r.scheduled_at,
            assigned_by=r.assigned_by,
            notes=r.notes,
            created_at=r.created_at,
        )

    async def create(self, assignment: OrderAssignment) -> OrderAssignment:
        from app.modules.orders.infra.models import OrderAssignmentModel
        model = OrderAssignmentModel(
            id=assignment.id,
            order_id=assignment.order_id,
            ally_id=assignment.ally_id,
            scheduled_at=assignment.scheduled_at,
            assigned_by=assignment.assigned_by,
            notes=assignment.notes,
            created_at=assignment.created_at,
        )
        self._session.add(model)
        await self._session.commit()
        return assignment

    async def get_latest(self, *, order_id: UUID) -> Optional[OrderAssignment]:
        """Devuelve la asignación más reciente de una orden (la activa)."""
        from app.modules.orders.infra.models import OrderAssignmentModel
        stmt = (
            select(OrderAssignmentModel)
            .where(OrderAssignmentModel.order_id == order_id)
            .order_by(desc(OrderAssignmentModel.created_at))
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return self._row_to_domain(row) if row else None

    async def list_by_order(self, *, order_id: UUID) -> list[OrderAssignment]:
        """Historial completo de asignaciones de una orden."""
        from app.modules.orders.infra.models import OrderAssignmentModel
        stmt = (
            select(OrderAssignmentModel)
            .where(OrderAssignmentModel.order_id == order_id)
            .order_by(desc(OrderAssignmentModel.created_at))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_domain(r) for r in rows]
