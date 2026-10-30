"""Feature 0011: resumen de clientes desde sus órdenes (gasto pagado, frecuencia, segmentos).
SQLite en memoria para el repositorio de lectura."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.catalog.infra.models import BreedModel
from app.modules.crm.app.use_cases import BuildCustomers, GetCustomer, GetCustomerStats, ListCustomers
from app.modules.crm.domain.customers import Visit, compute_metrics, segment_for
from app.modules.crm.infra.postgres_customer_read_repository import PostgresCustomerReadRepository
from app.modules.iam.infra.models import UserAddressModel, UserModel
from app.modules.orders.infra.models import OrderModel
from app.modules.pets.infra.models import PetModel

TODAY = date(2026, 10, 20)


def _run(coro):
    return asyncio.run(coro)


def _visit(day: date, amount=100.0) -> Visit:
    return Visit(order_id=uuid4(), day=day, pet_id=None, service_name="Baño", addon_names=[], amount=amount, paid=True)


# ─── Reglas de segmento (las de la maqueta) ──────────────────────────────────

@pytest.mark.parametrize("kwargs,expected", [
    (dict(services=3, days_since=80, days_since_first=200, interval=30, services_last_6m=3), "inactivo"),
    (dict(services=3, days_since=50, days_since_first=110, interval=30, services_last_6m=3), "en_riesgo"),
    (dict(services=3, days_since=40, days_since_first=100, interval=30, services_last_6m=3), "recurrente"),
    (dict(services=1, days_since=10, days_since_first=10, interval=None, services_last_6m=1), "nuevo"),
    (dict(services=1, days_since=40, days_since_first=40, interval=None, services_last_6m=1), "sin_recompra"),
    (dict(services=6, days_since=5, days_since_first=150, interval=15, services_last_6m=6), "vip"),
    # Frecuencia de 40 días: en riesgo recién pasados 60 (1,5 × 40)
    (dict(services=3, days_since=55, days_since_first=135, interval=40, services_last_6m=3), "recurrente"),
    (dict(services=3, days_since=61, days_since_first=141, interval=40, services_last_6m=3), "en_riesgo"),
])
def test_segment_rules(kwargs, expected):
    assert segment_for(**kwargs) == expected


def test_metrics_from_visits():
    visits = [_visit(TODAY - timedelta(days=d), amount=a) for d, a in [(60, 85), (30, 89.5), (0, 105)]]
    m = compute_metrics(visits, today=TODAY)
    assert (m.services, m.spend, m.avg_ticket) == (3, 279.5, 93.17)
    assert (m.first_visit, m.last_visit, m.days_since_last_visit, m.avg_interval_days) == (
        TODAY - timedelta(days=60), TODAY, 0, 30)
    assert m.segment == "recurrente"
    empty = compute_metrics([], today=TODAY)
    assert (empty.services, empty.segment, empty.last_visit) == (0, None, None)


# ─── Repositorio + casos de uso ──────────────────────────────────────────────

def _user(session, first, last, *, phone=None, district=None):
    u = UserModel(id=uuid4(), email=f"{first.lower()}@correo.pe", role="user", is_active=True, first_name=first,
                  last_name=last, phone=phone, address_district_id=district, created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                  updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    session.add(u)
    return u


def _pet(session, owner, name, weight=12.0):
    p = PetModel(id=uuid4(), owner_id=owner.id, name=name, species="dog", breed_name="Shih Tzu", weight_kg=weight,
                 grooming_frequency="monthly", receive_reminders=True, created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                 updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    session.add(p)
    return p


def _order(session, owner, pet, *, day, total, status="done", payment="paid", parent=None, district="150122"):
    # 15:00 UTC = 10:00 en Lima, mismo día
    when = datetime(day.year, day.month, day.day, 15, tzinfo=timezone.utc)
    items = [{"kind": "service_base", "ref_id": str(uuid4()), "name": "Fresco y Limpio", "qty": 1,
              "unit_price": total, "meta": {"pet_id": str(pet.id)}},
             {"kind": "service_addon", "ref_id": str(uuid4()), "name": "Corte estético", "qty": 1, "unit_price": 0}]
    o = OrderModel(id=uuid4(), user_id=owner.id, status=status, items_snapshot=items, total_snapshot=Decimal(str(total)),
                   currency="PEN", delivery_address_snapshot={"district_id": district}, payment_status=payment,
                   parent_order_id=parent.id if parent else None, completed_at=when if status == "done" else None,
                   created_at=when, updated_at=when)
    session.add(o)
    return o


async def _setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[
            BreedModel.__table__, UserModel.__table__, UserAddressModel.__table__, PetModel.__table__,
            OrderModel.__table__,
        ])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    ana = _user(session, "Ana", "Quispe", phone="+51 987 654 321")
    luis = _user(session, "Luis", "Rojas", district="150131")
    _user(session, "Sin", "Servicios")
    luna, max_ = _pet(session, ana, "Luna"), _pet(session, luis, "Max", weight=30)
    await session.flush()
    session.add(UserAddressModel(id=uuid4(), user_id=ana.id, district_id="150122", address_line="Av. Larco 1",
                                 lat=0, lng=0, is_default=True, created_at=datetime.now(timezone.utc),
                                 updated_at=datetime.now(timezone.utc)))
    # Ana: 3 servicios cada ~30 días; el último tiene un cargo extra pagado y otro sin pagar
    _order(session, ana, luna, day=TODAY - timedelta(days=60), total=85)
    _order(session, ana, luna, day=TODAY - timedelta(days=30), total=85)
    last = _order(session, ana, luna, day=TODAY - timedelta(days=2), total=89)
    _order(session, ana, luna, day=TODAY - timedelta(days=2), total=10, status="created", parent=last)
    _order(session, ana, luna, day=TODAY - timedelta(days=2), total=7, status="created", payment="pending", parent=last)
    # Ana también tiene una orden cancelada y una en curso: no cuentan
    _order(session, ana, luna, day=TODAY - timedelta(days=1), total=85, status="cancelled")
    _order(session, ana, luna, day=TODAY, total=85, status="in_service")
    # Luis: un solo servicio hace 50 días
    _order(session, luis, max_, day=TODAY - timedelta(days=50), total=135)
    await session.commit()
    repo = PostgresCustomerReadRepository(session=session)
    return SimpleNamespace(engine=engine, session=session, repo=repo, ana=ana, luis=luis, luna=luna, last=last)


async def _close(ctx):
    await ctx.session.close()
    await ctx.engine.dispose()


def test_customers_from_orders():
    async def scenario():
        ctx = await _setup()
        customers = {c.user.first_name: c for c in await BuildCustomers(repo=ctx.repo).execute(today=TODAY)}
        assert set(customers) == {"Ana", "Luis"}  # sin servicios no aparece
        ana = customers["Ana"].metrics
        assert (ana.services, ana.spend, ana.segment, ana.avg_interval_days) == (3, 269.0, "recurrente", 29)
        assert customers["Ana"].district_name == "Miraflores"          # dirección principal
        assert customers["Luis"].district_id == "150131"                # perfil (sin dirección principal)
        assert customers["Luis"].metrics.segment == "sin_recompra"
        [newest] = [v for v in ana.visits if v.order_id == ctx.last.id]
        assert (newest.amount, newest.addon_names, newest.pet_id) == (99.0, ["Corte estético"], ctx.luna.id)
        await _close(ctx)
    _run(scenario())


def test_filters_sort_and_stats():
    async def scenario():
        ctx = await _setup()
        listing = ListCustomers(repo=ctx.repo)
        assert [c.user.first_name for c in await listing.execute(sort="spend")] == ["Ana", "Luis"]
        assert [c.user.first_name for c in await listing.execute(q="987654")] == ["Ana"]
        assert [c.user.first_name for c in await listing.execute(q="max")] == ["Luis"]
        assert [c.user.first_name for c in await listing.execute(q="quíspe")] == ["Ana"]
        assert [c.user.first_name for c in await listing.execute(district_id="150131")] == ["Luis"]
        with pytest.raises(HTTPException) as exc:
            await listing.execute(segment="oro")
        assert exc.value.detail["code"] == "SEGMENT_INVALID"

        stats = await GetCustomerStats(repo=ctx.repo).execute()
        assert (stats.customers, stats.pets, stats.with_repurchase) == (2, 2, 1)
        assert stats.total_spend == 404.0 and stats.avg_spend == 202.0
        assert sum(stats.by_segment.values()) == 2
        await _close(ctx)
    _run(scenario())


def test_customer_detail_even_without_services():
    async def scenario():
        ctx = await _setup()
        ana = await GetCustomer(repo=ctx.repo).execute(ctx.ana.id)
        assert ana.metrics.services == 3
        with pytest.raises(HTTPException) as exc:
            await GetCustomer(repo=ctx.repo).execute(uuid4())
        assert exc.value.status_code == 404
        await _close(ctx)
    _run(scenario())
