"""Feature 0024: Cierre mensual / P&L con datos reales. SQLite en memoria con los repositorios reales."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.timezone import LIMA_TZ
from app.modules.catalog.infra.models import BreedModel
from app.modules.finance.app.use_cases import BuildMonthlyPnl
from app.modules.finance.domain.pnl import month_period, net_of_igv, recipe_on
from app.modules.finance.infra.postgres_finance_read_repository import PostgresFinanceReadRepository
from app.modules.general_settings.domain.settings import SettingInvalid, validate_value
from app.modules.groomer_costs.infra.models import GroomerCostProfileModel
from app.modules.groomer_costs.infra.postgres_cost_repository import PostgresCostRepository
from app.modules.iam.infra.models import UserModel
from app.modules.inventory.app.use_cases import OrderConsumption
from app.modules.inventory.domain.inventory import RecipeCell, RecipeLine
from app.modules.inventory.infra.models import (
    MovementModel,
    RecipeCellModel,
    RecipeLineModel,
    RecipeModel,
    SupplyModel,
)
from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
from app.modules.invoicing.infra.models import InvoiceDocumentModel
from app.modules.orders.infra.models import OrderModel, OrderPetModel
from app.modules.pets.infra.models import PetModel
from app.modules.store.domain.pricing import FALLBACK_CATEGORY

TABLES = [BreedModel, OrderModel, OrderPetModel, PetModel, UserModel, InvoiceDocumentModel, SupplyModel, MovementModel,
          RecipeModel, RecipeCellModel, RecipeLineModel, GroomerCostProfileModel]
PRODUCT = uuid4()
ADDON = uuid4()


def lima(y, m, d, h=12, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=LIMA_TZ).astimezone(timezone.utc)


class Ctx:
    def __init__(self, session):
        self.session = session
        self.inventory = PostgresInventoryRepository(session=session)
        self.settings = {"igv_percent": 18, "pos_fee_card_percent": 4.0, "pos_fee_yape_percent": 3.0}

    async def add(self, obj):
        self.session.add(obj)
        await self.session.commit()
        return obj

    def use_case(self, today: date) -> BuildMonthlyPnl:
        async def setting(key):
            return self.settings.get(key)

        return BuildMonthlyPnl(
            repo=PostgresFinanceReadRepository(session=self.session), inventory_repo=self.inventory,
            cost_repo=PostgresCostRepository(session=self.session),
            consumption=OrderConsumption(repo=self.inventory, store_repo=None, pets_repo=None),
            settings=setting, today=lambda: today)

    async def order(self, user, *, completed=None, total=118, paid=True, method="card", groomer=None,
                    status="done", parent=None, addon=False, arrival=None, discount=None, updated=None):
        items = [{"kind": "service_base", "ref_id": str(PRODUCT), "name": "Baño", "qty": 1, "unit_price": total,
                  "meta": {"pet_weight_kg": 10}}]
        if addon:
            items.append({"kind": "service_addon", "ref_id": str(ADDON), "name": "Corte", "qty": 1, "unit_price": 0})
        if parent is not None:
            items = [{"kind": "price_adjustment", "name": "Ajuste por diferencia de peso", "qty": 1,
                      "unit_price": total}]
        return await self.add(OrderModel(
            user_id=user.id, status=status, items_snapshot=items, total_snapshot=Decimal(str(total)),
            payment_status="paid" if paid else "pending", payment_method=method if paid else None,
            groomer_id=groomer.id if groomer else None, completed_at=completed, parent_order_id=parent,
            measured_weight_kg=Decimal("10") if parent is None else None, discount_amount=discount,
            service_steps_log=[{"step": "reception", "started_at": arrival.isoformat()}] if arrival else None,
            updated_at=updated or completed or lima(2026, 11, 1)))

    async def recipe(self, version, minutes, created):
        cells = [RecipeCell(breed_category=FALLBACK_CATEGORY, weight_min=0, weight_max=100, labor_minutes=minutes,
                            lines=[RecipeLine(self.supply.id, 10)])]
        current = await self.inventory.current_recipes_for([PRODUCT])
        r = await self.inventory.save_recipe_version(
            target_type="product", target_id=PRODUCT, version=version, cells=cells, created_by=None,
            replaces=current[PRODUCT].id if PRODUCT in current else None)
        await self.session.execute(update(RecipeModel).where(RecipeModel.id == r.id).values(created_at=created))
        await self.session.commit()

    async def movement(self, type_, qty, day, *, order=None, voided=False):
        self.seq = getattr(self, "seq", 0) + 1   # en Postgres lo da la identidad
        return await self.add(MovementModel(
            seq=self.seq, occurred_on=day, type=type_, supply_id=self.supply.id, quantity=Decimal(str(qty)),
            unit_cost=Decimal("0.1"), order_id=order.id if order else None, reason="prueba",
            voided_at=datetime.now(timezone.utc) if voided else None))


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


async def _november(ctx):
    """Escenario de noviembre 2026 con un groomer de S/ 2000 al mes y 200 horas de servicio (S/ 10 la hora)."""
    ctx.supply = await ctx.inventory.create_supply(sku="INS-001", fields={
        "name": "Shampoo", "category": "cosmetic", "purchase_unit": "Galón", "purchase_content": Decimal("1000"),
        "consumption_unit": "ml", "purchase_cost": Decimal("100"), "min_stock": Decimal("0")})
    await ctx.recipe(1, 60, lima(2026, 11, 1, 0))
    await ctx.recipe(2, 90, lima(2026, 11, 20, 0))
    client = await ctx.add(UserModel(email="ana@correo.pe", role="user", first_name="Ana", last_name="Pérez"))
    groomer = await ctx.add(UserModel(email="g@paku.pe", role="groomer", first_name="Luis", last_name="Ríos"))
    await ctx.add(GroomerCostProfileModel(groomer_id=groomer.id, effective_from=date(2026, 1, 1),
                                          base_salary=Decimal("2000"), items=[], monthly_hours=Decimal("200"),
                                          driving_rest_hours=Decimal("0")))
    o = {}
    # A: con boleta, tarjeta, receta R1, 75 min reales
    o["a"] = await ctx.order(client, completed=lima(2026, 11, 10, 15, 15), groomer=groomer,
                             arrival=lima(2026, 11, 10, 14), discount=10)
    await ctx.add(InvoiceDocumentModel(
        order_id=o["a"].id, user_id=client.id, doc_type="03", series="B001", number="1", issue_date=date(2026, 11, 10),
        customer_doc_type="1", customer_doc_number="45678912", customer_name="Ana Pérez", taxable_amount=Decimal("100"),
        igv=Decimal("18"), total=Decimal("118"), currency="PEN", status="ACEPTADO", environment="test", lines=[]))
    # B: efectivo sin pagar, sin boleta, receta R2
    o["b"] = await ctx.order(client, completed=lima(2026, 11, 25), total=59, paid=False, groomer=groomer)
    # C: contratado en noviembre, realizado el 01/12 → diciembre
    o["c"] = await ctx.order(client, completed=lima(2026, 12, 1, 9), groomer=groomer)
    # D: Yape, con un adicional sin receta
    o["d"] = await ctx.order(client, completed=lima(2026, 11, 28), method="yape", groomer=groomer, addon=True)
    # Ajustes: uno pagado de A (venta) y uno sin pagar de B (por cobrar)
    o["adj_a"] = await ctx.order(client, total=11.8, parent=o["a"].id, status="created")
    o["adj_b"] = await ctx.order(client, total=5.9, parent=o["b"].id, status="created", paid=False)
    # E: pagada y cancelada en noviembre; F: sin terminar
    o["e"] = await ctx.order(client, status="cancelled", updated=lima(2026, 11, 15))
    o["f"] = await ctx.order(client, status="created", completed=None, updated=lima(2026, 11, 20))
    # Inventario: la compra no es costo; anulados y de diciembre no cuentan
    await ctx.movement("purchase", 1000, date(2026, 11, 5))
    await ctx.movement("consumption", -10, date(2026, 11, 10), order=o["a"])
    await ctx.movement("waste", -50, date(2026, 11, 12))
    await ctx.movement("waste", -40, date(2026, 11, 13), voided=True)
    await ctx.movement("adjustment", -20, date(2026, 11, 14))
    await ctx.movement("adjustment", 30, date(2026, 11, 16))
    await ctx.movement("consumption", -10, date(2026, 12, 1), order=o["c"])
    return o, groomer


def _lines(p):
    return {ln.key: ln for ln in p.lines}


def test_closed_month_lines_sources_and_recipe_by_date():
    async def scenario(ctx):
        o, groomer = await _november(ctx)
        p = await ctx.use_case(date(2026, 12, 10)).execute(month="2026-11")
        lines = _lines(p)
        assert not p.period.is_open

        # Ventas: servicios del mes y ajuste pagado; C es de diciembre, E (cancelada) y F no son venta
        assert {s.order_id for s in p.sales} == {o["a"].id, o["b"].id, o["d"].id, o["adj_a"].id}
        by_sale = {s.order_id: s for s in p.sales}
        assert (by_sale[o["a"].id].net, by_sale[o["a"].id].net_source, by_sale[o["a"].id].document) == \
            (100.0, "document", "B001-1")
        assert (by_sale[o["b"].id].net, by_sale[o["b"].id].net_source) == (50.0, "estimated")
        assert by_sale[o["adj_a"].id].day == date(2026, 11, 10)
        assert (lines["net_sales"].amount, lines["net_sales"].status) == (260.0, "estimated")
        assert p.sales_with_igv == 306.8 and p.discounts == 10.0

        # Costo: solo consumos (no la compra), mermas y ajustes de salida
        assert lines["supplies"].amount == 1.0
        assert (lines["shrinkage"].amount, lines["shrinkage"].count) == (7.0, 2)
        assert p.entry_adjustments == 3.0

        # Mano de obra: A con R1 (60 min), B con R2 (90 min) a S/ 10 la hora; D sin receta del adicional
        costs = {c.order_id: c for c in p.costs}
        assert (costs[o["a"].id].labor_minutes, costs[o["a"].id].labor_cost, costs[o["a"].id].recipes) == \
            (60, 10.0, ("Baño R1",))
        assert (costs[o["b"].id].labor_minutes, costs[o["b"].id].labor_cost) == (90, 15.0)
        assert costs[o["d"].id].labor_cost is None and costs[o["d"].id].missing == ("Corte",)
        assert costs[o["a"].id].supplies == 1.0
        assert (lines["labor"].amount, lines["labor"].status) == (25.0, "partial")

        # No utilizada: S/ 2000 del mes − S/ 25 asignados
        assert [(g.groomer_id, g.monthly_cost, g.assigned) for g in p.groomers] == [(groomer.id, 2000.0, 25.0)]
        assert lines["unabsorbed_labor"].amount == 1975.0

        # Comisión: A 118 × 4 % + ajuste 11.8 × 4 % + D 118 × 3 %; B (efectivo sin pagar) no paga
        assert lines["payment_fees"].amount == pytest.approx(4.72 + 0.47 + 3.54)
        assert lines["groomer_variable"].amount is None and lines["groomer_variable"].status == "not_configured"

        cost = 1.0 + 7.0 + 25.0 + 1975.0 + 8.73
        assert lines["service_cost"].amount == pytest.approx(cost)
        assert lines["gross_margin"].amount == pytest.approx(260 - cost)
        assert lines["gross_margin"].status == "partial"
        for key in ("operating_expenses", "depreciation", "taxes"):
            assert lines[key].amount is None and lines[key].status == "not_configured"
        assert lines["net_result"].status == "partial"

        # Tiempo real vs receta: solo A tiene llegada (75 min = S/ 12.50 vs S/ 10)
        lc = p.labor_comparison
        assert (lc.services, lc.recipe_cost, lc.real_cost, lc.variation) == (1, 10.0, 12.5, 2.5)

        # Por cobrar: B y el ajuste sin pagar de B; pagada y cancelada aparte
        assert p.receivable == 64.9 and set(p.receivable_orders) == {o["b"].id, o["adj_b"].id}
        assert [(c.order_id, c.total) for c in p.cancelled_paid] == [(o["e"].id, 118.0)]
    run(scenario)


def test_december_gets_the_service_contracted_in_november():
    async def scenario(ctx):
        o, _ = await _november(ctx)
        p = await ctx.use_case(date(2026, 12, 10)).execute(month="2026-12")
        assert [s.order_id for s in p.sales] == [o["c"].id]
        assert _lines(p)["supplies"].amount == 1.0
        # Mes abierto: costo del groomer prorrateado a 10 de 31 días
        assert p.period.is_open and p.groomers[0].monthly_cost == pytest.approx(2000 * 10 / 31, abs=0.01)
    run(scenario)


def test_missing_fee_percent_is_not_configured_and_future_month_is_empty():
    async def scenario(ctx):
        await _november(ctx)
        ctx.settings.update(pos_fee_card_percent=None, pos_fee_yape_percent=None)
        p = await ctx.use_case(date(2026, 12, 10)).execute(month="2026-11")
        fees = _lines(p)["payment_fees"]
        assert (fees.amount, fees.status) == (None, "not_configured")

        future = await ctx.use_case(date(2026, 12, 10)).execute(month="2027-01")
        assert future.sales == [] and future.groomers == [] and future.period.days_elapsed == 0
        assert _lines(future)["unabsorbed_labor"].status == "not_configured"
    run(scenario)


def test_domain_helpers():
    with pytest.raises(ValueError):
        month_period("2026-13", date(2026, 11, 26))
    p = month_period("2026-11", date(2026, 11, 26))
    assert (p.start, p.end, p.cut, p.is_open, p.days_elapsed) == (date(2026, 11, 1), date(2026, 11, 30),
                                                                    date(2026, 11, 26), True, 26)
    assert round(net_of_igv(75, 18), 2) == 63.56

    class R:
        def __init__(self, version, created):
            self.version, self.created_at = version, created
    r1, r2 = R(1, lima(2026, 11, 5)), R(2, lima(2026, 11, 20))
    assert recipe_on([r2, r1], lima(2026, 11, 10)) is r1
    assert recipe_on([r1, r2], lima(2026, 11, 21)) is r2
    assert recipe_on([r1, r2], lima(2026, 11, 1)) is r1       # anterior a la primera versión
    assert recipe_on([], lima(2026, 11, 1)) is None


def test_fee_settings_are_percentages():
    assert validate_value("pos_fee_card_percent", 3.44) == 3.44
    assert validate_value("pos_fee_yape_percent", "") is None
    with pytest.raises(SettingInvalid):
        validate_value("pos_fee_card_percent", 25)
