"""Feature 0012: costo del groomer (sueldo + cargos, horas de servicio, historial por fecha).
SQLite en memoria para el repositorio."""
import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.groomer_costs.app.use_cases import GetLaborRates, SaveCostProfile
from app.modules.groomer_costs.domain.costs import (
    CostItem,
    CostProfile,
    CostProfileInvalid,
    profile_on,
    reference_rate,
    validate_profile,
)
from app.modules.groomer_costs.infra.models import GroomerCostProfileModel
from app.modules.groomer_costs.infra.postgres_cost_repository import PostgresCostRepository
from app.modules.iam.infra.models import UserModel

ADMIN = uuid4()


def _run(coro):
    return asyncio.run(coro)


def _profile(day=date(2026, 10, 1), salary=2400.0, items=(), hours=192.0, driving=32.0) -> CostProfile:
    return CostProfile(id=uuid4(), groomer_id=uuid4(), effective_from=day, base_salary=salary, items=list(items),
                       monthly_hours=hours, driving_rest_hours=driving, created_at=datetime.now(timezone.utc))


def test_cost_per_service_hour_includes_charges_and_driving():
    p = _profile(items=[CostItem("EsSalud", "percent", 9), CostItem("Vacaciones", "percent", 4.17),
                        CostItem("Uniforme", "amount", 20)])
    assert p.monthly_cost == pytest.approx(2400 + 216 + 100.08 + 20)
    assert p.service_hours == 160
    assert p.cost_per_hour == pytest.approx(p.monthly_cost / 192)
    assert p.cost_per_service_hour == pytest.approx(p.monthly_cost / 160)


@pytest.mark.parametrize("kwargs,code", [
    (dict(base_salary=0), "SALARY_INVALID"),
    (dict(monthly_hours=0), "HOURS_INVALID"),
    (dict(driving_rest_hours=192), "DRIVING_HOURS_INVALID"),
    (dict(items=[CostItem(" ", "percent", 9)]), "ITEM_LABEL_REQUIRED"),
    (dict(items=[CostItem("EsSalud", "percent", 120)]), "ITEM_VALUE_INVALID"),
    (dict(items=[CostItem("Bono", "otro", 1)]), "ITEM_KIND_INVALID"),
])
def test_validation(kwargs, code):
    with pytest.raises(CostProfileInvalid) as exc:
        validate_profile(**{**dict(base_salary=2400, items=[], monthly_hours=192, driving_rest_hours=32), **kwargs})
    assert exc.value.code == code


def test_profile_on_date_and_reference_rate():
    old, new = _profile(day=date(2026, 9, 1), salary=2000), _profile(day=date(2026, 11, 1), salary=2600)
    assert profile_on([old, new], date(2026, 10, 15)) is old
    assert profile_on([old, new], date(2026, 11, 1)) is new
    assert profile_on([old, new], date(2026, 8, 31)) is None
    assert reference_rate([]) is None
    assert reference_rate([_profile(salary=1600, driving=0, hours=160), _profile(salary=3200, driving=0, hours=160)]) == 15


def test_save_profile_history_and_rates_sqlite():
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[UserModel.__table__, GroomerCostProfileModel.__table__])
        session = async_sessionmaker(engine, expire_on_commit=False)()
        now = datetime.now(timezone.utc)
        groomer = UserModel(id=uuid4(), email="g@paku.pe", role="groomer", is_active=True, first_name="Carlos",
                            last_name="Ríos", created_at=now, updated_at=now)
        client = UserModel(id=uuid4(), email="c@paku.pe", role="user", is_active=True, first_name="Ana",
                           last_name="Q", created_at=now, updated_at=now)
        session.add_all([groomer, client])
        await session.commit()
        repo = PostgresCostRepository(session=session)
        save = SaveCostProfile(repo=repo)
        base = dict(base_salary=2400, items=[{"label": "EsSalud", "kind": "percent", "value": 9}],
                    monthly_hours=192, driving_rest_hours=32, notes=None, actor_id=ADMIN)

        await save.execute(groomer_id=groomer.id, effective_from=date(2026, 10, 1), **base)
        # Misma fecha: corrige el registro (no crea otro)
        await save.execute(groomer_id=groomer.id, effective_from=date(2026, 10, 1), **{**base, "base_salary": 2500})
        await save.execute(groomer_id=groomer.id, effective_from=date(2026, 12, 1), **{**base, "base_salary": 2800})
        history = await repo.list_profiles(groomer_id=groomer.id)
        assert [(p.effective_from, p.base_salary) for p in history] == [(date(2026, 12, 1), 2800), (date(2026, 10, 1), 2500)]

        rates = await GetLaborRates(repo=repo).execute(day=date(2026, 11, 15))
        assert rates.reference == pytest.approx(2500 * 1.09 / 160)
        assert rates.rate_for(groomer.id) == (pytest.approx(2500 * 1.09 / 160), "groomer")
        assert rates.rate_for(uuid4())[1] == "reference"

        with pytest.raises(HTTPException) as exc:  # un cliente no es groomer
            await save.execute(groomer_id=client.id, effective_from=date(2026, 10, 1), **base)
        assert exc.value.detail["code"] == "GROOMER_NOT_FOUND"
        with pytest.raises(HTTPException) as exc:
            await save.execute(groomer_id=groomer.id, effective_from=date(2026, 10, 1), **{**base, "driving_rest_hours": 500})
        assert exc.value.detail["code"] == "DRIVING_HOURS_INVALID"
        await session.close()
        await engine.dispose()
    _run(scenario())


def test_no_profiles_means_no_rate():
    class _Empty:
        async def list_profiles(self, **_):
            return []

    rates = _run(GetLaborRates(repo=_Empty()).execute(day=date(2026, 10, 1)))
    assert rates.reference is None and rates.rate_for(uuid4()) == (None, "reference")
