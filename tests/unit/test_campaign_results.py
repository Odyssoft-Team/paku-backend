"""Feature 0017: resultados de las campañas. SQLite en memoria para el repositorio; costo estimado simulado."""
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.campaigns.app.use_cases import BuildCampaignResults
from app.modules.campaigns.domain.results import summarize
from app.modules.campaigns.infra.models import CampaignModel
from app.modules.campaigns.infra.postgres_campaign_repository import PostgresCampaignRepository
from app.modules.catalog.infra.models import BreedModel
from app.modules.iam.infra.models import UserModel
from app.modules.orders.infra.models import OrderModel
from app.modules.pets.infra.models import PetModel

T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _at(day, hour=15):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


def _user(session, first):
    u = UserModel(id=uuid4(), email=f"{first.lower()}@correo.pe", role="user", is_active=True, first_name=first,
                  last_name="Pérez", created_at=T0, updated_at=T0)
    session.add(u)
    return u


def _campaign(session, code):
    c = CampaignModel(id=uuid4(), code=code, name=code.title(), audience="todos", benefit_type="percent",
                      value=Decimal("10"), channels=[], starts_on=date(2026, 10, 1), status="active")
    session.add(c)
    return c


def _order(session, owner, *, created, total, discount=None, campaign=None, status="done", payment="paid",
           parent=None, completed=None):
    items = [{"kind": "service_base", "ref_id": str(uuid4()), "name": "Baño", "qty": 1,
              "unit_price": total + (discount or 0)}]
    o = OrderModel(id=uuid4(), user_id=owner.id, status=status, items_snapshot=items, total_snapshot=Decimal(str(total)),
                   currency="PEN", payment_status=payment, payment_method="card",
                   parent_order_id=parent.id if parent else None,
                   discount_amount=Decimal(str(discount)) if discount else None,
                   campaign_id=campaign.id if campaign else None,
                   completed_at=completed or (created if status == "done" else None), created_at=created,
                   updated_at=created)
    session.add(o)
    return o


async def _results():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[
            BreedModel.__table__, UserModel.__table__, PetModel.__table__, OrderModel.__table__, CampaignModel.__table__,
        ])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        ana, beto, caro = _user(session, "Ana"), _user(session, "Beto"), _user(session, "Caro")
        promo, vuelve = _campaign(session, "PROMO"), _campaign(session, "VUELVE")
        await session.flush()
        # Ana: primera vez con PROMO (nueva); usa PROMO otra vez, con un cargo extra pagado
        a1 = _order(session, ana, created=_at(2), total=90, discount=10, campaign=promo)
        _order(session, ana, created=_at(3), total=12, parent=a1, status="created")
        _order(session, ana, created=_at(20), total=45, discount=5, campaign=promo, status="accepted")
        # Beto ya tenía un servicio terminado antes: no es nuevo
        _order(session, beto, created=_at(1), total=100)
        _order(session, beto, created=_at(10), total=80, discount=20, campaign=promo)
        # No cuentan: sin pagar y cancelada
        _order(session, caro, created=_at(11), total=50, discount=5, campaign=promo, status="created", payment="pending")
        _order(session, caro, created=_at(12), total=50, discount=5, campaign=promo, status="cancelled")
        # Caro con VUELVE, nueva
        _order(session, caro, created=_at(15), total=60, discount=15, campaign=vuelve)
        await session.commit()

        costs = {a1.id: 40.0}  # la de Beto queda sin costo (sin receta)

        async def cost_of(order):
            return costs.get(order.id)

        results, total = await BuildCampaignResults(repo=PostgresCampaignRepository(session=session),
                                                    cost_of=cost_of).execute()
        return results, total, promo.id, vuelve.id
    finally:
        await session.close()
        await engine.dispose()


def test_campaign_results():
    results, total, promo, vuelve = asyncio.run(_results())
    p = results[promo]
    assert (p.sold, p.done, p.customers, p.new_customers) == (3, 2, 2, 1)
    assert (p.subtotal, p.discount, p.net, p.extra_paid, p.collected) == (250, 35, 215, 12, 227)
    assert p.discount_pct == 14.0
    # Solo la orden de Ana tiene costo: cobrado 102 − costo 40
    assert (p.costed, p.cost, p.margin, p.margin_pct) == (1, 40, 62, 60.8)
    v = results[vuelve]
    assert (v.sold, v.new_customers, v.cost, v.margin) == (1, 1, None, None)
    assert (total.sold, total.customers, total.new_customers, total.collected) == (4, 3, 2, 287)


def test_new_customer_counts_previous_services_of_other_campaigns():
    from app.modules.campaigns.domain.results import CampaignSale

    u = uuid4()
    sale = CampaignSale(order_id=uuid4(), campaign_id=uuid4(), user_id=u, bought_at=_at(10), done=False,
                        subtotal=100, discount=10, net=90, extra_paid=0, cost=None)
    assert summarize([sale], {}).new_customers == 1
    assert summarize([sale], {u: _at(5)}).new_customers == 0     # ya tenía un servicio terminado
    assert summarize([sale], {u: _at(12)}).new_customers == 1    # el primero fue después de comprar
    empty = summarize([], {})
    assert (empty.sold, empty.discount_pct, empty.cost, empty.margin_pct) == (0, None, None, None)
