"""Capturas del inventario (feature 0015). Solo se insertan y se leen."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.domain.snapshots import Snapshot, SnapshotLine
from app.modules.inventory.infra.models import SnapshotLineModel, SnapshotModel


def _f(value) -> float:
    return float(value) if value is not None else 0.0


class PostgresSnapshotRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_snapshot(m: SnapshotModel, lines: Optional[list[SnapshotLineModel]] = None) -> Snapshot:
        return Snapshot(
            id=m.id, cut_date=m.cut_date, kind=m.kind, frequency=m.frequency, taken_at=m.taken_at,
            created_by=m.created_by, supplies_count=m.supplies_count, total_value=_f(m.total_value),
            low_count=m.low_count, out_count=m.out_count,
            lines=[
                SnapshotLine(
                    supply_id=x.supply_id, sku=x.sku, name=x.name, category=x.category,
                    consumption_unit=x.consumption_unit, purchase_unit=x.purchase_unit, is_active=x.is_active,
                    stock=_f(x.stock), min_stock=_f(x.min_stock), unit_cost=_f(x.unit_cost), value=_f(x.value),
                    status=x.status,
                )
                for x in lines or []
            ],
        )

    async def has_scheduled(self, cut_date: date) -> bool:
        stmt = select(SnapshotModel.id).where(SnapshotModel.schedule_key == cut_date.isoformat())
        return (await self._session.execute(stmt)).first() is not None

    async def create(
        self, *, cut_date: date, kind: str, frequency: Optional[str], created_by: Optional[UUID],
        lines: list[SnapshotLine],
    ) -> Optional[Snapshot]:
        """Guarda la captura con sus líneas. None si ya existe la automática de ese corte."""
        header = SnapshotModel(
            cut_date=cut_date, kind=kind, frequency=frequency, created_by=created_by,
            schedule_key=cut_date.isoformat() if kind == "scheduled" else None,
            supplies_count=len(lines), total_value=Decimal(str(round(sum(x.value for x in lines), 2))),
            low_count=sum(1 for x in lines if x.status == "low"), out_count=sum(1 for x in lines if x.status == "out"),
        )
        self._session.add(header)
        try:
            await self._session.flush()
            rows = [
                SnapshotLineModel(
                    snapshot_id=header.id, supply_id=x.supply_id, sku=x.sku, name=x.name, category=x.category,
                    consumption_unit=x.consumption_unit, purchase_unit=x.purchase_unit, is_active=x.is_active,
                    stock=Decimal(str(x.stock)), min_stock=Decimal(str(x.min_stock)),
                    unit_cost=Decimal(str(round(x.unit_cost, 6))), value=Decimal(str(round(x.value, 2))),
                    status=x.status,
                )
                for x in lines
            ]
            self._session.add_all(rows)
            await self._session.commit()
        except IntegrityError:  # otra instancia ya tomó la captura de este corte
            await self._session.rollback()
            return None
        await self._session.refresh(header)
        return self._to_snapshot(header, rows)

    async def list(self, *, date_from: Optional[date] = None, date_to: Optional[date] = None) -> list[Snapshot]:
        stmt = select(SnapshotModel).order_by(desc(SnapshotModel.cut_date), desc(SnapshotModel.taken_at))
        if date_from is not None:
            stmt = stmt.where(SnapshotModel.cut_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(SnapshotModel.cut_date <= date_to)
        return [self._to_snapshot(m) for m in (await self._session.execute(stmt)).scalars().all()]

    async def get(self, snapshot_id: UUID) -> Optional[Snapshot]:
        m = await self._session.get(SnapshotModel, snapshot_id)
        if m is None:
            return None
        stmt = select(SnapshotLineModel).where(SnapshotLineModel.snapshot_id == m.id).order_by(SnapshotLineModel.sku)
        return self._to_snapshot(m, list((await self._session.execute(stmt)).scalars().all()))
