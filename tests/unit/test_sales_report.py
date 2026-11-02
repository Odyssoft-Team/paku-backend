"""Feature 0016: reporte de ventas (servicios vendidos). SQLite en memoria para el repositorio de lectura."""
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.campaigns.infra.models import CampaignModel
from app.modules.catalog.infra.models import BreedModel
from app.modules.iam.infra.models import UserModel
from app.modules.orders.infra.models import OrderModel
from app.modules.pets.infra.models import PetModel
from app.modules.reports.app.use_cases import BuildSalesReport
from app.modules.reports.domain.sales import SalesFilters
from app.modules.reports.infra.postgres_sales_read_repository import PostgresSalesReadRepository

T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
BATH, CUT = str(uuid4()), str(uuid4())


def _run(coro):
    return asyncio.run(coro)


def _user(session, first, role="user"):
    u = UserModel(id=uuid4(), email=f"{first.lower()}@correo.pe", role=role, is_active=True, first_name=first,
                  last_name="Pérez", phone="+51 999 111 222", created_at=T0, updated_at=T0)
    session.add(u)
    return u


def _order(session, owner, pet, *, created, service=(BATH, "Baño"), addons=(), total, status="done", payment="paid",
           method="card", parent=None, discount=None, campaign=None, groomer=None, completed=None, district="150122"):
    items = [{"kind": "service_base", "ref_id": service[0], "name": service[1], "qty": 1,
              "unit_price": total + (discount or 0) - sum(p for _, p in addons), "meta": {"pet_id": str(pet.id)}}]
    items += [{"kind": "service_addon", "ref_id": str(uuid4()), "name": n, "qty": 1, "unit_price": p} for n, p in addons]
    o = OrderModel(id=uuid4(), user_id=owner.id, status=status, items_snapshot=items, total_snapshot=Decimal(str(total)),
                   currency="PEN", delivery_address_snapshot={"district_id": district}, payment_status=payment,
                   payment_method=method, parent_order_id=parent.id if parent else None,
                   discount_amount=Decimal(str(discount)) if discount else None,
                   campaign_id=campaign.id if campaign else None, groomer_id=groomer.id if groomer else None,
                   completed_at=completed, created_at=created, updated_at=created)
    session.add(o)
    return o


async def _report(**filters):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[
            BreedModel.__table__, UserModel.__table__, PetModel.__table__, OrderModel.__table__, CampaignModel.__table__,
        ])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        ana, beto, gro = _user(session, "Ana"), _user(session, "Beto"), _user(session, "Gabo", role="groomer")
        luna = PetModel(id=uuid4(), owner_id=ana.id, name="Luna", species="dog", breed_name="Shih Tzu",
                        weight_kg=10, grooming_frequency="monthly", receive_reminders=True, created_at=T0, updated_at=T0)
        max_ = PetModel(id=uuid4(), owner_id=beto.id, name="Max", species="dog", breed_name="Labrador",
                        weight_kg=30, grooming_frequency="monthly", receive_reminders=True, created_at=T0, updated_at=T0)
        promo = CampaignModel(id=uuid4(), code="PROMO10", name="Promo 10 %", audience="todos", benefit_type="percent",
                              value=Decimal("10"), channels=[], starts_on=date(2026, 10, 1), status="active")
        session.add_all([luna, max_, promo])
        await session.flush()
        # 10/10 20:00 en Lima = 11/10 01:00 UTC: cuenta el 10 de octubre
        a1 = _order(session, ana, luna, created=datetime(2026, 10, 11, 1, tzinfo=timezone.utc), total=90,
                    addons=[("Corte", 20)], discount=10, campaign=promo, groomer=gro,
                    completed=datetime(2026, 10, 14, 16, tzinfo=timezone.utc))
        _order(session, ana, luna, created=datetime(2026, 10, 14, 15, tzinfo=timezone.utc), total=12, parent=a1)
        _order(session, ana, luna, created=datetime(2026, 10, 14, 15, tzinfo=timezone.utc), total=5, parent=a1,
               payment="pending")
        _order(session, beto, max_, created=datetime(2026, 10, 20, 15, tzinfo=timezone.utc), service=(CUT, "Corte full"),
               total=150, status="created", payment="pending", method="cash")
        _order(session, beto, max_, created=datetime(2026, 10, 25, 15, tzinfo=timezone.utc), total=85, status="cancelled")
        _order(session, beto, max_, created=datetime(2026, 9, 30, 15, tzinfo=timezone.utc), total=85,
               completed=datetime(2026, 10, 1, 15, tzinfo=timezone.utc))
        await session.commit()
        return await BuildSalesReport(repo=PostgresSalesReadRepository(session=session)).execute(SalesFilters(**filters))
    finally:
        await session.close()
        await engine.dispose()


def test_sales_by_purchase_date():
    r = _run(_report(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31)))
    assert r.totals.orders == 3                          # la de septiembre y los cargos extra no son filas
    first = next(x for x in r.rows if x.customer_name == "Ana Pérez")
    assert first.purchase_date == date(2026, 10, 10)     # hora de Lima
    assert (first.subtotal, first.discount, first.total, first.extra_paid, first.collected) == (100, 10, 90, 12, 102)
    assert (first.pet_name, first.addon_names, first.campaign_name, first.groomer_name) == (
        "Luna", ["Corte"], "Promo 10 %", "Gabo Pérez")
    assert first.service_date == date(2026, 10, 14)
    t = r.totals
    assert (t.subtotal, t.discount, t.total, t.extra_paid, t.collected, t.cancelled) == (335, 10, 325, 12, 187, 1)
    assert t.avg_ticket == 93.5                         # 187 ÷ 2 pagadas (la cancelada sigue pagada)
    assert [(g.label, g.orders) for g in r.by_service] == [("Baño", 2), ("Corte full", 1)]
    assert {o[1] for o in r.options["campaigns"]} == {"Promo 10 %"}


def test_sales_filters_and_service_date():
    r = _run(_report(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), payment_status="paid"))
    assert r.totals.orders == 2
    r = _run(_report(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), q="max", payment_method="cash"))
    assert [x.service_name for x in r.rows] == ["Corte full"]
    r = _run(_report(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), service_id=CUT))
    assert r.totals.orders == 1
    # Por fecha del servicio: la comprada el 30/09 se realizó el 1/10; las que no tienen fecha de servicio no entran
    r = _run(_report(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), date_basis="service"))
    assert sorted(x.purchase_date for x in r.rows) == [date(2026, 9, 30), date(2026, 10, 10)]


def test_sales_invalid_filters():
    with pytest.raises(HTTPException):
        _run(_report(date_basis="paid"))
    with pytest.raises(HTTPException):
        _run(_report(date_from=date(2026, 10, 31), date_to=date(2026, 10, 1)))
