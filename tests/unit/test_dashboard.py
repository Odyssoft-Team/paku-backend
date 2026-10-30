"""Feature 0014: dashboard gerencial (mes al día vs. mismo corte del mes anterior).
SQLite en memoria para los repositorios de lectura; el costo por orden es un doble."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.booking.infra.models import AvailabilitySlotModel
from app.modules.crm.infra.postgres_customer_read_repository import PostgresCustomerReadRepository
from app.modules.dashboard.app.use_cases import BuildDashboard, arrival_offset_minutes
from app.modules.dashboard.domain.dashboard import (
    ESTIMATED,
    NO_DATA,
    REAL,
    Figure,
    Period,
    delta,
    lima_bounds,
    month_to_date,
)
from app.modules.dashboard.infra.postgres_dashboard_read_repository import PostgresDashboardReadRepository
from app.modules.orders.infra.models import OrderDelayReportModel, OrderModel
from app.modules.store.infra.db_models import CategoryModel, ProductModel  # FK de availability_slots

CUT = date(2026, 10, 20)


def _run(coro):
    return asyncio.run(coro)


# ─── Período ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cut,current,previous", [
    (date(2026, 10, 20), (date(2026, 10, 1), date(2026, 10, 20)), (date(2026, 9, 1), date(2026, 9, 20))),
    (date(2026, 3, 31), (date(2026, 3, 1), date(2026, 3, 31)), (date(2026, 2, 1), date(2026, 2, 28))),
    (date(2028, 3, 31), (date(2028, 3, 1), date(2028, 3, 31)), (date(2028, 2, 1), date(2028, 2, 29))),
    (date(2026, 1, 15), (date(2026, 1, 1), date(2026, 1, 15)), (date(2025, 12, 1), date(2025, 12, 15))),
])
def test_month_to_date(cut, current, previous):
    cur, prev = month_to_date(cut)
    assert (cur.date_from, cur.date_to) == current
    assert (prev.date_from, prev.date_to) == previous


def test_lima_bounds_are_utc():
    start, end = lima_bounds(Period(date(2026, 10, 1), date(2026, 10, 20)))
    assert start == datetime(2026, 10, 1, 5, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 21, 5, tzinfo=timezone.utc)


def test_delta():
    assert delta(Figure(30, REAL), Figure(20, REAL)) == (10, 50.0)
    assert delta(Figure(5, REAL), Figure(0, REAL)) == (5, None)
    assert delta(Figure(None, NO_DATA), Figure(20, REAL)) == (None, None)


def test_arrival_offset():
    o = SimpleNamespace(scheduled_at=datetime(2026, 10, 5, 14, 50),
                        service_steps_log=[{"step": "reception", "started_at": "2026-10-05T15:00:00+00:00"}])
    assert arrival_offset_minutes(o) == 10.0
    assert arrival_offset_minutes(SimpleNamespace(scheduled_at=None, service_steps_log=[])) is None


# ─── Escenario completo ─────────────────────────────────────────────────────

def _at(day: date, hour=15, minute=0):
    # 15:00 UTC = 10:00 en Lima, mismo día
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)


def _order(session, user, *, day, total, status="done", payment="paid", parent=None, **extra):
    o = OrderModel(id=uuid4(), user_id=user, status=status, items_snapshot=[], total_snapshot=Decimal(str(total)),
                   currency="PEN", payment_status=payment, parent_order_id=parent.id if parent else None,
                   completed_at=_at(day) if status == "done" else None, created_at=_at(day), updated_at=_at(day),
                   **extra)
    session.add(o)
    return o


async def _setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[
            CategoryModel.__table__, ProductModel.__table__, AvailabilitySlotModel.__table__,
            OrderModel.__table__, OrderDelayReportModel.__table__,
        ])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    ana, beto, carla = uuid4(), uuid4(), uuid4()
    oct5 = date(2026, 10, 5)
    # Ana: primer servicio en septiembre; en octubre uno con cargo extra pagado (y otro sin pagar) y tiempos
    a_sep = _order(session, ana, day=date(2026, 9, 10), total=85)
    a_oct = _order(session, ana, day=oct5, total=89, departed_at=_at(oct5, 14, 30), scheduled_at=_at(oct5, 14, 50),
                   service_steps_log=[{"step": "reception", "started_at": _at(oct5).isoformat()}])
    a_oct.completed_at = _at(oct5, 16)
    _order(session, ana, day=oct5, total=10, status="created", parent=a_oct)
    _order(session, ana, day=oct5, total=7, status="created", payment="pending", parent=a_oct)
    # Beto: cliente nuevo, pago en efectivo sin confirmar (por cobrar) y sin receta (sin costo)
    b_oct = _order(session, beto, day=date(2026, 10, 12), total=120, payment="pending")
    # Carla: vino en agosto y vuelve en octubre (recompra)
    _order(session, carla, day=date(2026, 8, 15), total=100)
    c_oct = _order(session, carla, day=date(2026, 10, 15), total=100)
    # Cancelaciones: cuentan solo las pagadas o en verificación
    _order(session, carla, day=date(2026, 10, 8), total=85, status="cancelled")
    _order(session, carla, day=date(2026, 10, 9), total=85, status="cancelled", payment="pending")
    _order(session, beto, day=date(2026, 9, 5), total=85, status="cancelled", payment="verifying")
    # Servicios solicitados: dos pagados (uno este mes, otro el próximo) y uno sin pagar (no cuenta)
    _order(session, beto, day=CUT, total=85, status="created", reserved_date=date(2026, 10, 22))
    _order(session, beto, day=CUT, total=85, status="skipped", scheduled_at=_at(date(2026, 11, 2)))
    _order(session, carla, day=CUT, total=85, status="created", payment="pending", reserved_date=date(2026, 10, 21))
    # Cupos (dos servicios el mismo día se suman) y un día inactivo que no cuenta
    for day, cap, booked, active in [(date(2026, 10, 3), 4, 3, True), (date(2026, 10, 4), 10, 0, False),
                                     (date(2026, 9, 3), 4, 1, True), (date(2026, 10, 21), 3, 1, True),
                                     (date(2026, 10, 21), 2, 1, True)]:
        session.add(AvailabilitySlotModel(id=uuid4(), service_id=uuid4(), date=day, capacity=cap, booked=booked,
                                          is_active=active))
    await session.flush()
    session.add(OrderDelayReportModel(id=uuid4(), order_id=a_oct.id, groomer_id=uuid4(), delay_minutes=15,
                                      created_at=_at(oct5, 14)))
    await session.commit()
    costs = {a_sep.id: 30.0, a_oct.id: 50.0, b_oct.id: None, c_oct.id: 40.0}

    async def cost_of(order):
        return costs.get(order.id)

    use_case = BuildDashboard(repo=PostgresDashboardReadRepository(session=session),
                              customers_repo=PostgresCustomerReadRepository(session=session), cost_of=cost_of)
    return SimpleNamespace(engine=engine, session=session, use_case=use_case)


async def _build():
    ctx = await _setup()
    try:
        return await ctx.use_case.execute(cut=CUT)
    finally:
        await ctx.session.close()
        await ctx.engine.dispose()


def test_dashboard_current_month():
    d = _run(_build())
    f = {k: (v.value, v.quality) for k, v in d.current.items()}
    assert f["services_done"] == (3, REAL)
    assert f["revenue"] == (319, REAL)            # 89 + 10 de cargo extra pagado + 120 + 100
    assert f["avg_ticket"] == (106.33, REAL)
    assert f["receivable"] == (120, REAL)
    assert f["cancellations"] == (1, REAL)
    assert f["occupancy"] == (75.0, REAL)         # 3 de 4 (el día inactivo no cuenta)
    assert f["new_customers"] == (1, REAL)        # Beto
    assert f["returning_customers"] == (2, REAL)  # Ana y Carla
    assert f["contribution"] == (109, ESTIMATED)  # (99 − 50) + (100 − 40); Beto sin datos
    assert (d.current["contribution"].with_data, d.current["contribution"].total) == (2, 3)
    assert f["contribution_pct"] == (54.8, ESTIMATED)
    assert f["avg_travel_minutes"] == (30.0, REAL)
    assert f["avg_service_minutes"] == (60.0, REAL)
    assert f["avg_arrival_offset_minutes"] == (10.0, REAL)
    assert (d.current["avg_travel_minutes"].with_data, d.current["avg_travel_minutes"].total) == (1, 3)
    assert f["delay_reports"] == (1, REAL)


def test_dashboard_previous_month_and_outlook():
    d = _run(_build())
    assert (d.previous_period.date_from, d.previous_period.date_to) == (date(2026, 9, 1), date(2026, 9, 20))
    p = {k: (v.value, v.quality) for k, v in d.previous.items()}
    assert p["services_done"] == (1, REAL)
    assert p["revenue"] == (85, REAL)
    assert p["new_customers"] == (1, REAL)        # Ana
    assert p["returning_customers"] == (0, REAL)
    assert p["cancellations"] == (1, REAL)
    assert p["occupancy"] == (25.0, REAL)
    assert p["contribution"] == (55, ESTIMATED)
    assert p["avg_travel_minutes"] == (None, NO_DATA)
    assert delta(d.current["services_done"], d.previous["services_done"]) == (2, 200.0)

    assert d.scheduled_rest_of_month == 1         # el del 22; el del 2 de noviembre es otro mes
    assert [x.day for x in d.next_days] == [CUT + timedelta(days=i) for i in range(7)]
    by_day = {x.day: x for x in d.next_days}
    assert (by_day[date(2026, 10, 21)].capacity, by_day[date(2026, 10, 21)].booked) == (5, 2)
    assert by_day[date(2026, 10, 21)].occupancy_pct == 40.0
    assert by_day[date(2026, 10, 21)].scheduled == 0   # la orden sin pagar no cuenta
    assert by_day[date(2026, 10, 22)].scheduled == 1
    assert (by_day[CUT].capacity, by_day[CUT].occupancy_pct) == (None, None)


def test_empty_month_has_no_data():
    async def run():
        ctx = await _setup()
        try:
            return await ctx.use_case.execute(cut=date(2026, 7, 10))
        finally:
            await ctx.session.close()
            await ctx.engine.dispose()

    d = _run(run())
    assert (d.current["services_done"].value, d.current["services_done"].quality) == (0, REAL)
    for key in ("avg_ticket", "occupancy", "contribution", "contribution_pct", "avg_service_minutes"):
        assert (d.current[key].value, d.current[key].quality) == (None, NO_DATA)
