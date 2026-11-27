"""Feature 0026: gastos operativos y vehículos. SQLite en memoria con el repositorio real."""
import asyncio
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.timezone import today_lima
from app.modules.expenses.app.use_cases import ListExpenses, SaveExpense, SaveVehicle, VoidExpense
from app.modules.expenses.infra.models import ExpenseModel, VehicleModel
from app.modules.expenses.infra.postgres_expenses_repository import PostgresExpensesRepository

ADMIN = uuid4()


async def _igv():
    return 18


def run(fn):
    async def wrapper():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[VehicleModel.__table__, ExpenseModel.__table__])
        session = async_sessionmaker(engine, expire_on_commit=False)()
        try:
            return await fn(PostgresExpensesRepository(session=session))
        finally:
            await session.close()
            await engine.dispose()
    return asyncio.run(wrapper())


def _code(exc_info):
    return exc_info.value.status_code, exc_info.value.detail.get("code"), exc_info.value.detail.get("field")


def test_vehicles_plate_is_unique_and_normalized():
    async def scenario(repo):
        save = SaveVehicle(repo=repo)
        van = await save.execute(None, fields={"name": "Paku 01", "plate": " abc-123 ", "year": 2024})
        assert van.plate == "ABC-123"
        with pytest.raises(HTTPException) as exc:
            await save.execute(None, fields={"name": "Otra", "plate": "abc-123"})
        assert _code(exc)[:2] == (409, "PLATE_EXISTS")
        with pytest.raises(HTTPException) as exc:
            await save.execute(None, fields={"name": "  "})
        assert _code(exc) == (422, "EXPENSE_INVALID", "name")
        edited = await save.execute(van.id, fields={"plate": "ABC-123", "is_active": False})
        assert edited.is_active is False and edited.name == "Paku 01"
    run(scenario)


def test_expense_validation_igv_edit_and_void():
    async def scenario(repo):
        save = SaveExpense(repo=repo, igv_percent=_igv)
        base = {"kind": "one_time", "category": "fuel", "description": "Grifo", "start_date": date(2026, 11, 5),
                "total_paid": 118, "igv_included": True}
        e = await save.execute(None, fields=base, actor_id=ADMIN)
        assert (e.amount, e.total_paid) == (100.0, 118.0)

        for bad, field in (({"kind": "weekly"}, "kind"), ({"category": "x"}, "category"),
                           ({"description": " "}, "description"), ({"total_paid": 0}, "total_paid"),
                           ({"start_date": today_lima() + timedelta(days=2)}, "start_date"),
                           ({"kind": "monthly", "end_date": date(2026, 10, 1)}, "end_date"),   # fin antes del inicio
                           ({"vehicle_id": uuid4()}, "vehicle_id")):
            with pytest.raises(HTTPException) as exc:
                await save.execute(None, fields={**base, **bad}, actor_id=ADMIN)
            assert _code(exc) == (422, "EXPENSE_INVALID", field), bad

        # Mensual con fin; cambiar a único quita el fin
        m = await save.execute(None, fields={**base, "kind": "monthly", "category": "internet_phone",
                                             "end_date": date(2027, 3, 31)}, actor_id=ADMIN)
        assert m.end_date == date(2027, 3, 31)
        assert (await save.execute(m.id, fields={"kind": "one_time"}, actor_id=ADMIN)).end_date is None

        edited = await save.execute(e.id, fields={"total_paid": 59, "igv_included": False}, actor_id=ADMIN)
        assert (edited.amount, edited.description) == (59.0, "Grifo")
        voided = await VoidExpense(repo=repo).execute(e.id, reason="Duplicado", actor_id=ADMIN)
        assert voided.is_voided
        with pytest.raises(HTTPException) as exc:
            await save.execute(e.id, fields={"total_paid": 10}, actor_id=ADMIN)
        assert _code(exc)[:2] == (409, "EXPENSE_VOIDED")
    run(scenario)


def test_list_in_period_gives_each_expense_its_part():
    async def scenario(repo):
        save = SaveExpense(repo=repo, igv_percent=_igv)
        await save.execute(None, fields={"kind": "monthly", "category": "internet_phone", "description": "Internet",
                                         "start_date": date(2026, 10, 1), "total_paid": 90, "igv_included": False},
                           actor_id=ADMIN)
        await save.execute(None, fields={"kind": "one_time", "category": "fuel", "description": "Octubre",
                                         "start_date": date(2026, 10, 20), "total_paid": 50, "igv_included": False},
                           actor_id=ADMIN)
        rows = await ListExpenses(repo=repo).execute(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31))
        assert [(r.expense.description, r.in_period) for r in rows] == [("Octubre", 50.0), ("Internet", 90.0)]
        rows = await ListExpenses(repo=repo).execute(date_from=date(2026, 9, 1), date_to=date(2026, 9, 30))
        assert rows == []                                          # aún no empezaban
        assert len(await ListExpenses(repo=repo).execute()) == 2
    run(scenario)
