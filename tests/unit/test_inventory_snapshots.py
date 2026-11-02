"""Feature 0015: capturas del inventario (frecuencia, corte, idempotencia y contenido).
SQLite en memoria para el repositorio de capturas; insumos y movimientos con un doble en memoria."""
import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.general_settings.domain.settings import SettingInvalid, validate_value
from app.modules.inventory.app.snapshots import RunScheduledSnapshot, TakeSnapshot
from app.modules.inventory.domain.inventory import Supply
from app.modules.inventory.domain.snapshots import due_cut, is_cut_day, next_cut
from app.modules.inventory.infra.models import SnapshotLineModel, SnapshotModel
from app.modules.inventory.infra.postgres_snapshot_repository import PostgresSnapshotRepository

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


# ─── Días de corte ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("day,frequency,expected", [
    (date(2026, 11, 1), "weekly", True),        # domingo
    (date(2026, 11, 2), "weekly", False),
    (date(2026, 11, 15), "semimonthly", True),
    (date(2026, 11, 30), "semimonthly", True),
    (date(2026, 11, 16), "semimonthly", False),
    (date(2026, 2, 28), "monthly", True),
    (date(2028, 2, 28), "monthly", False),      # bisiesto: el fin de mes es el 29
    (date(2026, 10, 31), "none", False),
])
def test_is_cut_day(day, frequency, expected):
    assert is_cut_day(day, frequency) is expected


def test_due_and_next_cut():
    # El corte del 31/10 se toma al terminar el día: el 1/11 ya está pendiente
    assert due_cut(date(2026, 11, 1), "monthly") == date(2026, 10, 31)
    assert due_cut(date(2026, 10, 31), "monthly") is None
    assert due_cut(date(2026, 11, 3), "monthly") == date(2026, 10, 31)
    assert due_cut(date(2026, 11, 4), "monthly") is None        # más de 3 días: se pierde
    assert due_cut(date(2026, 11, 2), "weekly") == date(2026, 11, 1)
    assert due_cut(date(2026, 11, 2), "none") is None
    assert next_cut(date(2026, 11, 1), "weekly") == date(2026, 11, 1)
    assert next_cut(date(2026, 11, 2), "semimonthly") == date(2026, 11, 15)
    assert next_cut(date(2026, 11, 2), "none") is None


def test_frequency_setting_is_a_choice():
    assert validate_value("inventory_snapshot_frequency", "weekly") == "weekly"
    assert validate_value("inventory_snapshot_frequency", None) is None
    with pytest.raises(SettingInvalid):
        validate_value("inventory_snapshot_frequency", "daily")


# ─── Captura ────────────────────────────────────────────────────────────────

def _supply(sku, name, *, cost=100.0, content=1000.0, min_stock=200.0, active=True):
    return Supply(id=uuid4(), sku=sku, name=name, category="cosmetic", purchase_unit="Botella",
                  purchase_content=content, consumption_unit="ml", purchase_cost=cost, min_stock=min_stock,
                  tracks_lot=False, tracks_expiry=False, is_active=active, created_at=NOW, updated_at=NOW)


@dataclass
class _Inventory:
    supplies: list
    movements: list = field(default_factory=list)   # (supply_id, día, cantidad)

    async def list_supplies(self, *, include_inactive=True):
        return [s for s in self.supplies if include_inactive or s.is_active]

    async def stock_by_supply(self, *, until=None):
        out = {}
        for sid, day, qty in self.movements:
            if until is None or day <= until:
                out[sid] = out.get(sid, 0.0) + qty
        return out


@dataclass
class _Settings:
    values: dict = field(default_factory=dict)

    async def get(self, key):
        return self.values.get(key)


async def _ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[SnapshotModel.__table__, SnapshotLineModel.__table__])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    shampoo = _supply("INS-001", "Shampoo")
    gloves = _supply("INS-002", "Guantes", cost=32, content=100, min_stock=50)
    old = _supply("INS-003", "Colonia vieja", active=False)
    empty_old = _supply("INS-004", "Toalla descontinuada", active=False)
    inv = _Inventory([shampoo, gloves, old, empty_old], [
        (shampoo.id, date(2026, 10, 2), 1000), (shampoo.id, date(2026, 10, 20), -850),
        (gloves.id, date(2026, 10, 2), 100), (gloves.id, date(2026, 10, 25), -100),
        (old.id, date(2026, 9, 1), 300),
        (shampoo.id, date(2026, 11, 1), 500),          # después del corte: no entra
    ])
    return engine, session, inv, PostgresSnapshotRepository(session=session), (shampoo, gloves, old)


def test_snapshot_freezes_stock_at_cut():
    async def run():
        engine, session, inv, snaps, (shampoo, gloves, old) = await _ctx()
        try:
            snap = await TakeSnapshot(repo=inv, snapshots=snaps).execute(cut_date=date(2026, 10, 31), kind="manual")
            again = await snaps.get(snap.id)
            return snap, again, shampoo, gloves, old
        finally:
            await session.close()
            await engine.dispose()

    snap, again, shampoo, gloves, old = _run(run())
    lines = {x.sku: x for x in again.lines}
    assert sorted(lines) == ["INS-001", "INS-002", "INS-003"]   # el inactivo sin stock no entra
    assert (lines["INS-001"].stock, lines["INS-001"].status, lines["INS-001"].value) == (150, "low", 15.0)
    assert (lines["INS-002"].stock, lines["INS-002"].status, lines["INS-002"].value) == (0, "out", 0)
    assert (lines["INS-003"].stock, lines["INS-003"].is_active, lines["INS-003"].status) == (300, False, "ok")
    assert (again.supplies_count, again.total_value, again.low_count, again.out_count) == (3, 45.0, 1, 1)
    assert (again.kind, again.cut_date) == ("manual", date(2026, 10, 31))


def test_scheduled_snapshot_once_per_cut():
    async def run():
        engine, session, inv, snaps, _ = await _ctx()
        try:
            use_case = RunScheduledSnapshot(repo=inv, snapshots=snaps, settings_repo=_Settings())  # Fin de mes
            first = await use_case.execute(today=date(2026, 11, 1))
            second = await use_case.execute(today=date(2026, 11, 1))
            # Aunque otra instancia lo intente a la vez, la clave única deja una sola
            dup = await TakeSnapshot(repo=inv, snapshots=snaps).execute(cut_date=date(2026, 10, 31), kind="scheduled")
            manual = await TakeSnapshot(repo=inv, snapshots=snaps).execute(cut_date=date(2026, 10, 31), kind="manual")
            not_cut = await use_case.execute(today=date(2026, 10, 31))
            off = await RunScheduledSnapshot(repo=inv, snapshots=snaps, settings_repo=_Settings(
                {"inventory_snapshot_frequency": "none"})).execute(today=date(2026, 11, 1))
            items = await snaps.list(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31))
            return first, second, dup, manual, not_cut, off, items
        finally:
            await session.close()
            await engine.dispose()

    first, second, dup, manual, not_cut, off, items = _run(run())
    assert (first.cut_date, first.kind, first.frequency) == (date(2026, 10, 31), "scheduled", "monthly")
    assert second is None and dup is None and not_cut is None and off is None
    assert manual is not None                       # las manuales no chocan con la automática
    assert sorted(s.kind for s in items) == ["manual", "scheduled"]
