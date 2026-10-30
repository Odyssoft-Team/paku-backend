"""Feature 0013: campañas de descuento por segmento (mejor oferta, cupón, usos, liberar al cancelar).
SQLite en memoria para los repositorios de campañas y de clientes."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.campaigns.app.use_cases import CampaignEngine, ListCampaigns, SaveCampaign
from app.modules.campaigns.domain.campaigns import (
    Buyer,
    Campaign,
    Offer,
    PurchaseLine,
    audience_matches,
    best_offer,
    discount_for,
    display_state,
)
from app.modules.campaigns.infra.models import CampaignModel, CampaignRedemptionModel
from app.modules.campaigns.infra.postgres_campaign_repository import PostgresCampaignRepository
from app.modules.catalog.infra.models import BreedModel
from app.modules.crm.infra.postgres_customer_read_repository import PostgresCustomerReadRepository
from app.modules.iam.infra.models import UserAddressModel, UserModel
from app.modules.orders.infra.models import OrderModel
from app.modules.pets.infra.models import PetModel

TODAY = date(2026, 10, 20)
ADMIN = uuid4()
ADDON_ID = uuid4()


def _run(coro):
    return asyncio.run(coro)


def _c(**f) -> Campaign:
    base = dict(id=uuid4(), code="X", name="X", objective=None, audience="todos", benefit_type="percent", value=10,
                addon_code=None, channels=[], starts_on=date(2026, 10, 1), ends_on=None, status="active",
                automatic=True, max_uses_per_customer=1, max_total_uses=None,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    return Campaign(**{**base, **f})


LINES = [PurchaseLine("service_base", 135), PurchaseLine("service_addon", 25, "ADD_DESLANADO_INT")]


# ─── Reglas puras ────────────────────────────────────────────────────────────

def test_display_state():
    assert display_state(_c(status="draft"), today=TODAY) == "borrador"
    assert display_state(_c(starts_on=date(2026, 11, 1)), today=TODAY) == "programada"
    assert display_state(_c(), today=TODAY) == "activa"
    assert display_state(_c(status="paused"), today=TODAY) == "pausada"
    assert display_state(_c(ends_on=date(2026, 10, 19)), today=TODAY) == "finalizada"
    assert display_state(_c(max_total_uses=5), today=TODAY, total_uses=5) == "finalizada"


def test_discounts_never_exceed_subtotal():
    assert discount_for(_c(value=10), LINES) == 16.0
    assert discount_for(_c(benefit_type="amount", value=15), LINES) == 15.0
    assert discount_for(_c(benefit_type="amount", value=500), LINES) == 160.0
    assert discount_for(_c(benefit_type="free_addon", addon_code="ADD_DESLANADO_INT"), LINES) == 25.0
    assert discount_for(_c(benefit_type="free_addon", addon_code="ADD_CORTE_EST"), LINES) == 0.0


def test_audiences():
    new_client = Buyer(segment=None, services=0, pet_birth_month=10)
    regular = Buyer(segment="recurrente", services=4, pet_birth_month=3)
    assert audience_matches("primera_compra", new_client, today=TODAY)
    assert not audience_matches("primera_compra", regular, today=TODAY)
    assert audience_matches("recurrente", regular, today=TODAY)
    assert audience_matches("cumpleanos", new_client, today=TODAY) and not audience_matches("cumpleanos", regular, today=TODAY)
    assert audience_matches("todos", regular, today=TODAY)


def test_best_offer_is_the_biggest_discount():
    a, b = _c(code="A"), _c(code="B")
    assert best_offer([Offer(a, 10), Offer(b, 15)]).campaign is b
    assert best_offer([Offer(a, 0)]) is None


# ─── Repositorios + motor ────────────────────────────────────────────────────

class _Pets:
    def __init__(self, pet):
        self.pet = pet

    async def get_by_id(self, pet_id, include_deleted=False):
        return self.pet if pet_id == self.pet.id else None


class _Store:
    async def get_addon(self, addon_id):
        return SimpleNamespace(code="ADD_DESLANADO_INT") if addon_id == ADDON_ID else None


def _items(pet_id, price=135, addon=True):
    items = [{"kind": "service_base", "ref_id": str(uuid4()), "name": "Spa", "qty": 1, "unit_price": price,
              "meta": {"pet_id": str(pet_id)}}]
    if addon:
        items.append({"kind": "service_addon", "ref_id": str(ADDON_ID), "name": "Deslanado", "qty": 1, "unit_price": 25})
    return items


async def _setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[
            BreedModel.__table__, UserModel.__table__, UserAddressModel.__table__, PetModel.__table__,
            OrderModel.__table__, CampaignModel.__table__, CampaignRedemptionModel.__table__,
        ])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    now = datetime.now(timezone.utc)
    user = UserModel(id=uuid4(), email="ana@correo.pe", role="user", is_active=True, first_name="Ana", last_name="Q",
                     created_at=now, updated_at=now)
    pet = PetModel(id=uuid4(), owner_id=user.id, name="Luna", species="dog", birth_date=date(2020, 10, 5),
                   created_at=now, updated_at=now)
    session.add_all([user, pet])
    await session.commit()
    repo = PostgresCampaignRepository(session=session)
    eng = CampaignEngine(repo=repo, crm_repo=PostgresCustomerReadRepository(session=session),
                         pets_repo=_Pets(SimpleNamespace(id=pet.id, birth_date=pet.birth_date)), store_repo=_Store())
    return SimpleNamespace(engine=engine, session=session, repo=repo, eng=eng, user=user, pet=pet)


async def _close(ctx):
    await ctx.session.close()
    await ctx.engine.dispose()


async def _campaign(ctx, **f):
    base = dict(code="X", name="X", audience="todos", benefit_type="percent", value=10, starts_on=date(2026, 10, 1),
                status="active", automatic=True, max_uses_per_customer=1)
    return await SaveCampaign(repo=ctx.repo).execute({**base, **f}, actor_id=ADMIN)


async def _order(ctx, *, payment="paid", status="created", hours_ago=0):
    when = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    o = OrderModel(id=uuid4(), user_id=ctx.user.id, status=status, items_snapshot=[], total_snapshot=Decimal("100"),
                   currency="PEN", payment_status=payment, created_at=when, updated_at=when)
    ctx.session.add(o)
    await ctx.session.commit()
    return o


def test_save_campaign_validates_and_normalizes():
    async def scenario():
        ctx = await _setup()
        c = await _campaign(ctx, code="bienvenida10", benefit_type="amount", value=15, addon_code="ADD_X")
        assert (c.code, c.addon_code) == ("BIENVENIDA10", None)  # el adicional solo aplica a free_addon
        with pytest.raises(HTTPException) as exc:
            await _campaign(ctx, code="BIENVENIDA10")
        assert exc.value.detail["code"] == "CAMPAIGN_CODE_TAKEN"
        for bad, code in [({"value": 120}, "CAMPAIGN_VALUE_INVALID"), ({"audience": "oro"}, "CAMPAIGN_AUDIENCE_INVALID"),
                          ({"benefit_type": "free_addon"}, "CAMPAIGN_ADDON_REQUIRED"),
                          ({"ends_on": date(2026, 9, 1)}, "CAMPAIGN_DATES_INVALID")]:
            with pytest.raises(HTTPException) as exc:
                await _campaign(ctx, code=f"OTRO{code[-5:]}", **bad)
            assert exc.value.detail["code"] == code
        edited = await SaveCampaign(repo=ctx.repo).execute({"status": "paused"}, campaign_id=c.id, actor_id=ADMIN)
        assert (edited.status, edited.value) == ("paused", 15)
        await _close(ctx)
    _run(scenario())


def test_engine_picks_best_automatic_and_validates_code():
    async def scenario():
        ctx = await _setup()
        await _campaign(ctx, code="BIENVENIDA", audience="primera_compra", value=10)          # S/ 16
        await _campaign(ctx, code="CUMPLE", audience="cumpleanos", benefit_type="free_addon",
                        addon_code="ADD_DESLANADO_INT")                                         # S/ 25
        await _campaign(ctx, code="VIP20", audience="vip", value=20, automatic=False)
        await _campaign(ctx, code="PAKU30", value=30, automatic=False)                          # S/ 48 con cupón
        await _campaign(ctx, code="BORRADOR", status="draft", value=90)

        quote = await ctx.eng.quote(user_id=ctx.user.id, items_snapshot=_items(ctx.pet.id), today=TODAY)
        assert (quote.subtotal, quote.discount, quote.total, quote.offer.campaign.code) == (160, 25, 135, "CUMPLE")

        with_code = await ctx.eng.quote(user_id=ctx.user.id, items_snapshot=_items(ctx.pet.id), code="paku30", today=TODAY)
        assert (with_code.discount, with_code.offer.campaign.code) == (48, "PAKU30")

        for code, error in [("NOEXISTE", "CAMPAIGN_CODE_NOT_FOUND"), ("BORRADOR", "CAMPAIGN_CODE_NOT_FOUND"),
                            ("VIP20", "CAMPAIGN_NOT_FOR_CUSTOMER")]:
            with pytest.raises(HTTPException) as exc:
                await ctx.eng.quote(user_id=ctx.user.id, items_snapshot=_items(ctx.pet.id), code=code, today=TODAY)
            assert exc.value.detail["code"] == error
        # Cupón de adicional gratis sin ese adicional en la compra
        await _campaign(ctx, code="CORTE", benefit_type="free_addon", addon_code="ADD_CORTE_EST", automatic=False)
        with pytest.raises(HTTPException) as exc:
            await ctx.eng.quote(user_id=ctx.user.id, items_snapshot=_items(ctx.pet.id), code="CORTE", today=TODAY)
        assert exc.value.detail["code"] == "CAMPAIGN_NOT_APPLICABLE"
        await _close(ctx)
    _run(scenario())


def test_uses_per_customer_and_release_on_cancel():
    async def scenario():
        ctx = await _setup()
        c = await _campaign(ctx, code="UNAVEZ", value=10, automatic=False, max_uses_per_customer=1)
        paid = await _order(ctx)
        await ctx.repo.add_redemption(campaign_id=c.id, order_id=paid.id, user_id=ctx.user.id, discount=16)
        with pytest.raises(HTTPException) as exc:
            await ctx.eng.quote(user_id=ctx.user.id, items_snapshot=_items(ctx.pet.id), code="UNAVEZ", today=TODAY)
        assert exc.value.detail["code"] == "CAMPAIGN_ALREADY_USED"

        # Cancelar la orden libera el uso
        assert await ctx.repo.release_for_order(paid.id) is True
        quote = await ctx.eng.quote(user_id=ctx.user.id, items_snapshot=_items(ctx.pet.id), code="UNAVEZ", today=TODAY)
        assert quote.discount == 16

        # Una orden pendiente abandonada (más de 2 h) no quema el cupón; una reciente sí cuenta
        old = await _order(ctx, payment="pending", hours_ago=3)
        await ctx.repo.add_redemption(campaign_id=c.id, order_id=old.id, user_id=ctx.user.id, discount=16)
        assert (await ctx.repo.uses([c.id])).get(c.id, 0) == 0
        recent = await _order(ctx, payment="pending")
        await ctx.repo.add_redemption(campaign_id=c.id, order_id=recent.id, user_id=ctx.user.id, discount=16)
        assert (await ctx.repo.uses([c.id], user_id=ctx.user.id))[c.id] == 1
        await _close(ctx)
    _run(scenario())


def test_order_saves_net_total_and_redemption():
    """CreateOrderFromCart: total_snapshot = subtotal − descuento; queda el uso de la campaña."""
    from app.modules.campaigns.app.use_cases import Quote
    from app.modules.cart.domain.cart import CartStatus
    from app.modules.orders.app.use_cases import CreateOrderFromCart

    campaign = _c(code="PAKU15", benefit_type="amount", value=15)
    pet_id = uuid4()
    redemptions = []

    class _Orders:
        _session = None  # notificaciones best effort
        created = None

        async def list_unpaid_adjustments(self, *, user_id):
            return []

        async def create_order(self, order):
            self.created = order
            return order

        async def add_order_pets(self, **_):
            pass

    class _Cart:
        async def get_cart(self, *, cart_id, user_id):
            return SimpleNamespace(status=CartStatus.checked_out)

        async def list_items(self, *, cart_id, user_id):
            return [SimpleNamespace(id=uuid4(), cart_id=cart_id, kind="service_base", ref_id=uuid4(), name="Spa", qty=1,
                                    unit_price=135.0, meta={"pet_id": str(pet_id)})]

    class _Engine:
        repo = SimpleNamespace(add_redemption=lambda **kw: _async(redemptions.append(kw)))

        async def quote(self, *, user_id, items_snapshot, code=None):
            return Quote(subtotal=135.0, offer=Offer(campaign, 15.0))

    async def _async(value):
        return value

    orders = _Orders()
    order = _run(CreateOrderFromCart(orders_repo=orders, cart_repo=_Cart(), campaign_engine=_Engine()).execute(
        user_id=uuid4(), cart_id=uuid4(), delivery_address_snapshot={}, campaign_code="PAKU15"))
    assert (order.total_snapshot, order.discount_amount, order.campaign_id) == (120.0, 15.0, campaign.id)
    assert redemptions == [{"campaign_id": campaign.id, "order_id": order.id, "user_id": order.user_id, "discount": 15.0}]


def test_list_with_results_and_audience_size():
    async def scenario():
        ctx = await _setup()
        c = await _campaign(ctx, code="BIENVENIDA", audience="primera_compra")
        await _campaign(ctx, code="CUMPLE", audience="cumpleanos", benefit_type="amount", value=5)
        paid = await _order(ctx)
        await ctx.repo.add_redemption(campaign_id=c.id, order_id=paid.id, user_id=ctx.user.id, discount=16)
        rows = {r.campaign.code: r for r in await ListCampaigns(repo=ctx.repo, crm_repo=PostgresCustomerReadRepository(
            session=ctx.session)).execute(today=TODAY)}
        assert (rows["BIENVENIDA"].paid_uses, rows["BIENVENIDA"].discount_given, rows["BIENVENIDA"].sales) == (1, 16, 100)
        assert rows["BIENVENIDA"].audience_size == 1   # Ana no tiene servicios terminados
        assert rows["CUMPLE"].audience_size == 1       # Luna nació en octubre
        assert rows["BIENVENIDA"].state == "activa"
        await _close(ctx)
    _run(scenario())
