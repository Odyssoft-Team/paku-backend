"""Capturas del inventario (feature 0015): tomar la foto del stock al corte y consultarla."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.timezone import today_lima
from app.modules.inventory.app.use_cases import supply_row
from app.modules.inventory.domain.snapshots import DEFAULT_FREQUENCY, Snapshot, SnapshotLine, due_cut

logger = logging.getLogger(__name__)


@dataclass
class TakeSnapshot:
    repo: Any              # PostgresInventoryRepository (insumos y stock)
    snapshots: Any         # PostgresSnapshotRepository

    async def execute(
        self, *, cut_date: date, kind: str, frequency: Optional[str] = None, actor_id: Optional[UUID] = None,
    ) -> Optional[Snapshot]:
        """Stock de cada insumo con los movimientos hasta `cut_date` (incluido). Entran los insumos activos y los
        inactivos que aún tienen stock. None si la captura automática de ese corte ya existía."""
        stock = await self.repo.stock_by_supply(until=cut_date)
        lines = []
        for supply in await self.repo.list_supplies(include_inactive=True):
            row = supply_row(supply, stock.get(supply.id, 0.0))
            if not supply.is_active and row.stock == 0:
                continue
            lines.append(SnapshotLine(
                supply_id=supply.id, sku=supply.sku, name=supply.name, category=supply.category,
                consumption_unit=supply.consumption_unit, purchase_unit=supply.purchase_unit,
                is_active=supply.is_active, stock=row.stock, min_stock=supply.min_stock,
                unit_cost=supply.unit_cost, value=round(row.value, 2), status=row.status,
            ))
        return await self.snapshots.create(cut_date=cut_date, kind=kind, frequency=frequency,
                                           created_by=actor_id, lines=lines)


async def snapshot_frequency(settings_repo: Any) -> str:
    from app.modules.general_settings.app.use_cases import get_setting

    return await get_setting(settings_repo, "inventory_snapshot_frequency") or DEFAULT_FREQUENCY


@dataclass
class RunScheduledSnapshot:
    repo: Any
    snapshots: Any
    settings_repo: Any

    async def execute(self, *, today: Optional[date] = None) -> Optional[Snapshot]:
        """Toma la captura automática del último corte terminado, si falta. Idempotente."""
        frequency = await snapshot_frequency(self.settings_repo)
        cut = due_cut(today or today_lima(), frequency)
        if cut is None or await self.snapshots.has_scheduled(cut):
            return None
        return await TakeSnapshot(repo=self.repo, snapshots=self.snapshots).execute(
            cut_date=cut, kind="scheduled", frequency=frequency,
        )


@dataclass
class GetSnapshot:
    snapshots: Any

    async def execute(self, snapshot_id: UUID) -> Snapshot:
        snap = await self.snapshots.get(snapshot_id)
        if snap is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "code": "SNAPSHOT_NOT_FOUND", "message": "Captura no encontrada.",
            })
        return snap


async def run_scheduled_snapshot_job() -> None:
    """Tarea del scheduler: cada 30 min revisa si falta la captura del último corte."""
    from app.core.db import AsyncSessionLocal
    from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository
    from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
    from app.modules.inventory.infra.postgres_snapshot_repository import PostgresSnapshotRepository

    try:
        async with AsyncSessionLocal() as session:
            snap = await RunScheduledSnapshot(
                repo=PostgresInventoryRepository(session=session),
                snapshots=PostgresSnapshotRepository(session=session),
                settings_repo=PostgresSettingsRepository(session=session),
            ).execute()
            if snap is not None:
                logger.info("inventory_snapshot cut=%s supplies=%s", snap.cut_date, snap.supplies_count)
    except Exception:
        logger.exception("inventory_snapshot_job failed")
