"""Feature 0025: no se vende un servicio sin insumos. SQLite en memoria con el repositorio real de inventario."""
import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.catalog.infra.models import BreedModel
from app.modules.inventory.app.availability import StockAvailability
from app.modules.inventory.app.use_cases import OrderConsumption
from app.modules.inventory.domain.availability import Shortage, merge, shortage_message, shortages
from app.modules.inventory.domain.inventory import ConsumptionTarget, RecipeCell, RecipeLine
from app.modules.inventory.infra.models import (
    MovementModel,
    RecipeCellModel,
    RecipeLineModel,
    RecipeModel,
    SupplyModel,
)
from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
from app.modules.orders.app.use_cases_impl.payment import PayOrder
from app.modules.orders.domain.order import Order
from app.modules.orders.infra.models import OrderModel, OrderPetModel
from app.modules.pets.infra.models import PetModel
from app.modules.store.domain.pricing import FALLBACK_CATEGORY
from datetime import date

TABLES = [BreedModel, OrderModel, OrderPetModel, PetModel, SupplyModel, MovementModel, RecipeModel,
          RecipeCellModel, RecipeLineModel]
BATH, CONDITIONER, NO_RECIPE = uuid4(), uuid4(), uuid4()


class Ctx:
    def __init__(self, session):
        self.session = session
        self.repo = PostgresInventoryRepository(session=session)
        self.seq = 0
        self.stock = StockAvailability(
            repo=self.repo, consumption=OrderConsumption(repo=self.repo, store_repo=None, pets_repo=None))

    def fresh(self):
        """Disponibilidad sin caché (otra petición)."""
        return StockAvailability(repo=self.repo, consumption=self.stock.consumption)

    async def supply(self, name, qty):
        s = await self.repo.create_supply(sku=f"INS-{uuid4().hex[:4]}", fields={
            "name": name, "category": "cosmetic", "purchase_unit": "Galón", "purchase_content": Decimal("1000"),
            "consumption_unit": "ml", "purchase_cost": Decimal("100"), "min_stock": Decimal("0")})
        self.seq += 1
        self.session.add(MovementModel(seq=self.seq, occurred_on=date(2026, 11, 1), type="initial_stock",
                                       supply_id=s.id, quantity=Decimal(str(qty)), unit_cost=Decimal("0.1"),
                                       reason="inicial"))
        await self.session.commit()
        return s

    async def recipe(self, target_id, target_type, supply, qty):
        cells = [RecipeCell(breed_category=FALLBACK_CATEGORY, weight_min=0, weight_max=100, labor_minutes=30,
                            lines=[RecipeLine(supply.id, qty)])]
        await self.repo.save_recipe_version(target_type=target_type, target_id=target_id, version=1, cells=cells,
                                            created_by=None)

    async def order(self, *, payment="paid", status="created", addon=False):
        items = [{"kind": "service_base", "ref_id": str(BATH), "name": "Baño", "qty": 1, "unit_price": 60,
                  "meta": {"pet_weight_kg": 10}}]
        if addon:
            items.append({"kind": "service_addon", "ref_id": str(CONDITIONER), "name": "Acondicionador", "qty": 1,
                          "unit_price": 20})
        o = OrderModel(user_id=uuid4(), status=status, items_snapshot=items, total_snapshot=Decimal("60"),
                       payment_status=payment)
        self.session.add(o)
        await self.session.commit()
        return o


async def _with_ctx(fn):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[m.__table__ for m in TABLES])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        return await fn(Ctx(session))
    finally:
        await session.close()
        await engine.dispose()


def run(fn):
    return asyncio.run(_with_ctx(fn))


BATH_T = ConsumptionTarget("product", str(BATH), "Baño")
COND_T = ConsumptionTarget("addon", str(CONDITIONER), "Acondicionador")


def test_sold_services_commit_supplies_until_the_last_one():
    """500 ml de shampoo, 100 ml por baño: con 4 baños vendidos queda 1; con 5, ninguno."""
    async def scenario(ctx):
        shampoo = await ctx.supply("Shampoo", 500)
        await ctx.recipe(BATH, "product", shampoo, 100)
        for _ in range(4):
            await ctx.order()
        await ctx.order(payment="verifying")                     # en verificación también está vendido
        await ctx.order(payment="pending")                       # sin pagar: no compromete
        await ctx.order(status="cancelled")                      # cancelada: no compromete
        await ctx.order(status="done")                           # realizada: ya registró (o registrará) su consumo
        assert (await ctx.stock.available())[shampoo.id] == 0.0
        result = await ctx.fresh().for_pet([BATH_T], breed_category=FALLBACK_CATEGORY, weight_kg=10)
        assert [(s.name, s.needed, s.available) for s in result[str(BATH)]] == [("Shampoo", 100.0, 0.0)]

        # Al comprar shampoo vuelve a estar disponible
        ctx.seq += 1
        ctx.session.add(MovementModel(seq=ctx.seq, occurred_on=date(2026, 11, 2), type="purchase", supply_id=shampoo.id,
                                      quantity=Decimal("100"), unit_cost=Decimal("0.1"), reason="compra"))
        await ctx.session.commit()
        result = await ctx.fresh().for_pet([BATH_T], breed_category=FALLBACK_CATEGORY, weight_kg=10)
        assert result[str(BATH)] == []
    run(scenario)


def test_addon_is_checked_with_its_service_and_no_recipe_is_sellable():
    async def scenario(ctx):
        shampoo = await ctx.supply("Shampoo", 150)
        conditioner = await ctx.supply("Acondicionador", 40)
        await ctx.recipe(BATH, "product", shampoo, 100)
        await ctx.recipe(CONDITIONER, "addon", conditioner, 50)
        no_recipe = ConsumptionTarget("addon", str(NO_RECIPE), "Corte de uñas")
        result = await ctx.stock.for_pet([COND_T, no_recipe], breed_category=FALLBACK_CATEGORY, weight_kg=10,
                                         base=BATH_T)
        assert [s.name for s in result[str(CONDITIONER)]] == ["Acondicionador"]
        assert result[str(NO_RECIPE)] == []                       # sin receta: se vende
        # Sin celda para el peso (más de 100 kg): se vende
        assert (await ctx.stock.for_pet([BATH_T], breed_category=FALLBACK_CATEGORY, weight_kg=120))[str(BATH)] == []
    run(scenario)


def test_order_shortages_counts_the_whole_order_but_not_itself():
    async def scenario(ctx):
        shampoo = await ctx.supply("Shampoo", 100)
        conditioner = await ctx.supply("Acondicionador", 50)
        await ctx.recipe(BATH, "product", shampoo, 100)
        await ctx.recipe(CONDITIONER, "addon", conditioner, 50)
        mine = await ctx.order(payment="pending", addon=True)
        assert await ctx.stock.order_shortages(mine) == []
        await ctx.order(addon=True)                                # otra la vende antes
        missing = await ctx.fresh().order_shortages(mine)
        assert [s.name for s in missing] == ["Acondicionador", "Shampoo"]
    run(scenario)


# ---------- Pago ----------

class _Orders:
    def __init__(self, order):
        self.order = order

    async def get_order(self, *, id, user_id):
        return self.order


class _Culqi:
    calls = 0

    async def create_charge(self, **_kw):
        self.calls += 1
        raise AssertionError("no debe cobrar")


class _Stock:
    def __init__(self, result=None, error=None):
        self.result, self.error = result or [], error

    async def order_shortages(self, order):
        if self.error:
            raise self.error
        return self.result


def test_pay_rejects_out_of_stock_before_charging():
    order = Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=60, currency="PEN")
    missing = [Shortage(uuid4(), "Shampoo", "ml", 100, 20)]
    culqi = _Culqi()
    use_case = PayOrder(orders_repo=_Orders(order), culqi_client=culqi, users_repo=None, districts_repo=None,
                        stock=_Stock(missing))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(use_case.execute(order_id=order.id, user_id=order.user_id, email="a@b.pe", source_id="tkn"))
    assert exc.value.status_code == 409 and exc.value.detail["code"] == "OUT_OF_STOCK"
    assert "shampoo" in exc.value.detail["message"] and exc.value.detail["supplies"] == ["Shampoo"]
    assert culqi.calls == 0


def test_pay_stock_check_skips_adjustments_and_never_blocks_on_its_own_error():
    from app.modules.orders.app.use_cases_impl.payment import _assert_stock

    adjustment = Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=10, currency="PEN",
                           parent_order_id=uuid4())
    asyncio.run(_assert_stock(adjustment, _Stock([Shortage(uuid4(), "Shampoo", "ml", 1, 0)])))
    service = Order.new(user_id=uuid4(), items_snapshot=[], total_snapshot=60, currency="PEN")
    asyncio.run(_assert_stock(service, _Stock(error=RuntimeError("bd caída"))))
    asyncio.run(_assert_stock(service, None))


def test_domain_rules():
    a, b = uuid4(), uuid4()

    class S:
        def __init__(self, name):
            self.name, self.consumption_unit = name, "ml"
    assert merge({a: 1}, {a: 2, b: 1}) == {a: 3, b: 1}
    found = shortages({a: 100, b: 10}, {a: 99.9999999, b: 5}, {a: S("Shampoo"), b: S("Algodón")})
    assert [s.name for s in found] == ["Algodón"]               # tolerancia decimal en el shampoo
    assert shortage_message(found) == "Falta Algodón"
