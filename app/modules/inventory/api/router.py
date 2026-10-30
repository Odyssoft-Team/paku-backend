"""Inventario (feature 0009): insumos, movimientos, recetas y costo por orden (insumos + mano de obra). Solo admin."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import engine, get_async_session
from app.modules.inventory.api.schemas import (
    CodeLabelOut,
    InventoryConfigOut,
    InventorySummaryOut,
    MissingRecipeOut,
    MovementCreateIn,
    MovementOut,
    OrderCostCellOut,
    OrderCostLineOut,
    OrderCostOut,
    RecipeCellOut,
    RecipeLineOut,
    RecipeOut,
    RecipeSaveIn,
    RecipeSummaryOut,
    SupplyCreateIn,
    SupplyOut,
    SupplyUpdateIn,
)
from app.modules.inventory.app.use_cases import (
    CreateSupply,
    GetInventorySummary,
    GetOrderCost,
    ListSupplies,
    OrderConsumption,
    RegisterMovement,
    SaveRecipe,
    SupplyRow,
    UpdateSupply,
    cell_supplies_cost,
    order_labor_rates,
)
from app.modules.inventory.domain.inventory import (
    CATEGORIES,
    CONSUMPTION_UNITS,
    COST_CENTERS,
    LOCATIONS,
    MOVEMENT_TYPES,
    Movement,
    Recipe,
    Supply,
)
from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

admin_router = APIRouter(prefix="/inventory", tags=["inventory-admin"])


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresInventoryRepository:
    return PostgresInventoryRepository(session=session)


def get_store_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresStoreRepository:
    return PostgresStoreRepository(session=session, engine=engine)


def get_pets_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresPetRepository:
    return PostgresPetRepository(session=session, engine=engine)


def get_orders_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderRepository:
    return PostgresOrderRepository(session=session, engine=engine)


# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

@admin_router.get("/config", response_model=InventoryConfigOut)
async def inventory_config(_: CurrentUser = Depends(require_roles("admin"))) -> InventoryConfigOut:
    """Listas fijas del inventario. Filas y tramos de las recetas: GET /admin/store/price-config."""
    return InventoryConfigOut(
        categories=[CodeLabelOut(code=k, label=v) for k, v in CATEGORIES.items()],
        consumption_units=list(CONSUMPTION_UNITS),
        movement_types=[CodeLabelOut(code=k, label=v[0]) for k, v in MOVEMENT_TYPES.items()],
        manual_movement_types=list(MOVEMENT_TYPES),
        locations=list(LOCATIONS),
        cost_centers=[CodeLabelOut(code=k, label=v) for k, v in COST_CENTERS.items()],
    )


# ------------------------------------------------------------------
# Insumos
# ------------------------------------------------------------------

def _supply_out(row: SupplyRow) -> SupplyOut:
    s = row.supply
    return SupplyOut(
        id=s.id, sku=s.sku, name=s.name, category=s.category, category_label=CATEGORIES.get(s.category, s.category),
        purchase_unit=s.purchase_unit, purchase_content=s.purchase_content, consumption_unit=s.consumption_unit,
        purchase_cost=s.purchase_cost, unit_cost=round(s.unit_cost, 6), min_stock=s.min_stock,
        tracks_lot=s.tracks_lot, tracks_expiry=s.tracks_expiry, is_active=s.is_active,
        stock=row.stock, status=row.status, value=round(row.value, 2), created_at=s.created_at, updated_at=s.updated_at,
    )


@admin_router.get("/supplies", response_model=list[SupplyOut])
async def list_supplies(
    include_inactive: bool = Query(True),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
) -> list[SupplyOut]:
    """Maestro de insumos con stock (suma de movimientos), estado y valor al día de hoy."""
    return [_supply_out(r) for r in await ListSupplies(repo=repo).execute(include_inactive=include_inactive)]


@admin_router.post("/supplies", response_model=SupplyOut, status_code=status.HTTP_201_CREATED)
async def create_supply(
    payload: SupplyCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
) -> SupplyOut:
    """Crea un insumo. El código (INS-001…) lo asigna el backend; el stock empieza en 0."""
    return _supply_out(await CreateSupply(repo=repo).execute(fields=payload.model_dump()))


@admin_router.patch("/supplies/{supply_id}", response_model=SupplyOut)
async def update_supply(
    supply_id: UUID,
    payload: SupplyUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
) -> SupplyOut:
    """Edita o desactiva (`is_active`) un insumo. Solo cambia lo enviado."""
    fields = {k: getattr(payload, k) for k in payload.model_fields_set}
    return _supply_out(await UpdateSupply(repo=repo).execute(supply_id, fields=fields))


# ------------------------------------------------------------------
# Movimientos
# ------------------------------------------------------------------

def _movement_out(m: Movement, supply: Optional[Supply]) -> MovementOut:
    return MovementOut(
        id=m.id, code=m.code, occurred_on=m.occurred_on, type=m.type,
        type_label=MOVEMENT_TYPES.get(m.type, (m.type, 0))[0], supply_id=m.supply_id,
        sku=supply.sku if supply else "", supply_name=supply.name if supply else "",
        consumption_unit=supply.consumption_unit if supply else "", quantity=m.quantity,
        unit_cost=m.unit_cost, cost=round(m.cost, 2), location=m.location, cost_center=m.cost_center,
        order_id=m.order_id, recipe_id=m.recipe_id, reason=m.reason, lot=m.lot, expires_on=m.expires_on,
        created_by=m.created_by, created_by_name=m.created_by_name, created_at=m.created_at,
    )


@admin_router.get("/movements", response_model=list[MovementOut])
async def list_movements(
    type: Optional[str] = Query(None, description="initial_stock|purchase|consumption|adjustment|waste"),
    supply_id: Optional[UUID] = Query(None),
    order_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
) -> list[MovementOut]:
    """Movimientos del más reciente al más antiguo (fecha y número)."""
    movements = await repo.list_movements(
        type=type, supply_id=supply_id, order_id=order_id, date_from=date_from, date_to=date_to, limit=limit,
    )
    supplies = await repo.get_supplies(list({m.supply_id for m in movements}))
    return [_movement_out(m, supplies.get(m.supply_id)) for m in movements]


@admin_router.post("/movements", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
async def register_movement(
    payload: MovementCreateIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
) -> MovementOut:
    """Registra un movimiento manual. No se editan ni se borran: los errores se corrigen con un ajuste."""
    movement = await RegisterMovement(repo=repo).execute(
        type=payload.type, supply_id=payload.supply_id, quantity=payload.quantity, direction=payload.direction,
        occurred_on=payload.occurred_on, location=payload.location, cost_center=payload.cost_center,
        order_id=payload.order_id, reason=payload.reason, lot=payload.lot, expires_on=payload.expires_on,
        actor_id=current.id,
    )
    return _movement_out(await repo.get_movement(movement.id) or movement, await repo.get_supply(movement.supply_id))


@admin_router.get("/summary", response_model=InventorySummaryOut)
async def inventory_summary(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
) -> InventorySummaryOut:
    """Valor del inventario y bajo mínimo (al día) y costo de los consumos por servicio del período."""
    summary = await GetInventorySummary(repo=repo).execute(date_from=date_from, date_to=date_to)
    return InventorySummaryOut(**summary.__dict__)


# ------------------------------------------------------------------
# Recetas (una tabla por servicio o adicional, como los precios)
# ------------------------------------------------------------------

async def _target_names(recipes: list[Recipe], store_repo) -> dict[UUID, str]:
    """Nombre de cada servicio, y de cada adicional con su servicio («Deslanado · Spa Deluxe»)."""
    out: dict[UUID, str] = {}
    for r in recipes:
        if r.target_id in out:
            continue
        if r.target_type == "product":
            product = await store_repo.get_product(r.target_id)
            out[r.target_id] = product.name if product else "Servicio eliminado"
        else:
            addon = await store_repo.get_addon(r.target_id)
            product = await store_repo.get_product(addon.product_id) if addon else None
            out[r.target_id] = f"{addon.name} · {product.name}" if addon and product else (addon.name if addon else "Adicional eliminado")
    return out


def _same(a: Optional[float], b: Optional[float]) -> bool:
    return a == b or (a is not None and b is not None and abs(a - b) < 0.005)


async def _recipe_out(recipe: Recipe, repo, store_repo, labor_rate: Optional[float], name: Optional[str]) -> RecipeOut:
    supplies = await repo.get_supplies(list({l.supply_id for c in recipe.cells for l in c.lines}))
    prices = [p for p in await store_repo.list_price_rules(target_id=recipe.target_id) if p.is_active]
    cells = []
    for c in recipe.cells:
        supplies_cost = cell_supplies_cost(c, supplies)
        labor = c.labor_minutes / 60 * labor_rate if labor_rate is not None else None
        total = supplies_cost + (labor or 0)
        price = next((float(p.price) for p in prices if p.breed_category == c.breed_category
                      and _same(p.weight_min, c.weight_min) and _same(p.weight_max, c.weight_max)), None)
        cells.append(RecipeCellOut(
            id=c.id, breed_category=c.breed_category, weight_min=c.weight_min, weight_max=c.weight_max,
            labor_minutes=c.labor_minutes,
            lines=[
                RecipeLineOut(
                    supply_id=l.supply_id, sku=supplies[l.supply_id].sku, supply_name=supplies[l.supply_id].name,
                    consumption_unit=supplies[l.supply_id].consumption_unit, quantity=l.quantity,
                    unit_cost=round(supplies[l.supply_id].unit_cost, 6),
                    cost=round(supplies[l.supply_id].unit_cost * l.quantity, 2),
                )
                for l in c.lines if l.supply_id in supplies
            ],
            supplies_cost=round(supplies_cost, 2), labor_cost=round(labor, 2) if labor is not None else None,
            total_cost=round(total, 2), price=price, margin=round(price - total, 2) if price is not None else None,
        ))
    return RecipeOut(
        id=recipe.id, target_type=recipe.target_type, target_id=recipe.target_id, target_name=name,
        version=recipe.version, version_label=recipe.version_label, is_current=recipe.is_current, cells=cells,
        labor_rate=round(labor_rate, 2) if labor_rate is not None else None, created_at=recipe.created_at,
    )


async def _reference_rate(session: AsyncSession) -> Optional[float]:
    from app.modules.groomer_costs.app.use_cases import labor_rates

    return (await labor_rates(session)).reference


@admin_router.get("/recipes", response_model=list[RecipeSummaryOut])
async def list_recipes(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> list[RecipeSummaryOut]:
    """Servicios y adicionales que ya tienen receta (versión vigente y cuántas celdas tiene)."""
    recipes = await repo.list_recipes(current_only=True)
    names = await _target_names(recipes, store_repo)
    return sorted(
        (RecipeSummaryOut(target_type=r.target_type, target_id=r.target_id, target_name=names.get(r.target_id),
                          version_label=r.version_label, cells=len(r.cells), created_at=r.created_at)
         for r in recipes),
        key=lambda s: (s.target_type != "product", s.target_name or ""),
    )


@admin_router.get("/recipes/{target_id}", response_model=Optional[RecipeOut])
async def get_recipe(
    target_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
    session: AsyncSession = Depends(get_async_session),
) -> Optional[RecipeOut]:
    """Tabla vigente del servicio o adicional, con costo por celda (insumos + mano de obra) y el precio de la
    misma celda. null si todavía no tiene receta."""
    recipe = (await repo.current_recipes_for([target_id])).get(target_id)
    if recipe is None:
        return None
    names = await _target_names([recipe], store_repo)
    return await _recipe_out(recipe, repo, store_repo, await _reference_rate(session), names.get(target_id))


@admin_router.get("/recipes/{target_id}/versions", response_model=list[RecipeOut])
async def recipe_versions(
    target_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
    session: AsyncSession = Depends(get_async_session),
) -> list[RecipeOut]:
    """Todas las versiones de la tabla (la más nueva primero), con los costos de hoy."""
    recipes = await repo.list_recipes(current_only=False, target_id=target_id)
    names = await _target_names(recipes, store_repo)
    rate = await _reference_rate(session)
    return [await _recipe_out(r, repo, store_repo, rate, names.get(r.target_id)) for r in recipes]


@admin_router.put("/recipes/{target_id}", response_model=RecipeOut)
async def save_recipe(
    target_id: UUID,
    payload: RecipeSaveIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
    session: AsyncSession = Depends(get_async_session),
) -> RecipeOut:
    """
    Guarda la tabla completa como la versión siguiente (R1 → R2). Mismas filas y tramos que la tabla de
    precios. Los consumos ya registrados no cambian. 409 `RECIPE_UNCHANGED` si no hay cambios.
    """
    recipe = await SaveRecipe(repo=repo, store_repo=store_repo).execute(
        target_type=payload.target_type, target_id=target_id,
        cells=[c.model_dump() for c in payload.cells], actor_id=current.id,
    )
    names = await _target_names([recipe], store_repo)
    return await _recipe_out(recipe, repo, store_repo, await _reference_rate(session), names.get(target_id))


# ------------------------------------------------------------------
# Costo y consumo por orden
# ------------------------------------------------------------------

async def _load_order(orders_repo: PostgresOrderRepository, order_id: UUID):
    order = await orders_repo.get_order_admin(id=order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _sum(*values: Optional[float]) -> Optional[float]:
    return None if any(v is None for v in values) else round(sum(values), 2)


@admin_router.get("/orders/{order_id}/cost", response_model=OrderCostOut)
async def order_cost(
    order_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
    pets_repo: PostgresPetRepository = Depends(get_pets_repo),
    orders_repo: PostgresOrderRepository = Depends(get_orders_repo),
    session: AsyncSession = Depends(get_async_session),
) -> OrderCostOut:
    """
    Costo de la orden: insumos (registrados si ya terminó, o estimados con las recetas vigentes) y mano de obra
    (minutos de la receta y tiempo real × costo por hora de servicio del groomer de la orden, o el de referencia).
    """
    order = await _load_order(orders_repo, order_id)
    rates = await order_labor_rates(session, order)
    cost = await GetOrderCost(repo=repo, store_repo=store_repo, pets_repo=pets_repo).execute(order, rates=rates)
    sale = float(order.total_snapshot)
    total_est = _sum(cost.supplies_cost, cost.labor_cost_estimated)
    total_real = _sum(cost.supplies_cost, cost.labor_cost_real)
    margin_est = round(sale - total_est, 2) if total_est is not None else None
    return OrderCostOut(
        order_id=order.id, status=order.status.value, sale_total=sale, breed_category=cost.plan.breed_category,
        weight_kg=cost.plan.weight_kg, registered=cost.registered,
        lines=[
            OrderCostLineOut(
                supply_id=line.supply.id, sku=line.supply.sku, supply_name=line.supply.name,
                consumption_unit=line.supply.consumption_unit, quantity=round(line.quantity, 3),
                unit_cost=round(line.unit_cost, 6), cost=round(line.cost, 2),
                recipe_id=line.recipe.id if line.recipe else None,
                recipe_version=line.recipe.version_label if line.recipe else None,
            )
            for line in cost.lines
        ],
        cells=[
            OrderCostCellOut(
                target_type=pc.target.target_type, ref_id=pc.target.ref_id, name=pc.target.name,
                recipe_id=pc.recipe.id, recipe_version=pc.recipe.version_label, breed_category=pc.category_used,
                weight_min=pc.cell.weight_min, weight_max=pc.cell.weight_max, labor_minutes=pc.cell.labor_minutes,
            )
            for pc in cost.plan.cells
        ],
        missing_recipes=[MissingRecipeOut(**t.__dict__) for t in cost.plan.missing],
        supplies_cost=cost.supplies_cost,
        labor_rate=round(cost.labor_rate, 2) if cost.labor_rate is not None else None,
        labor_rate_source=cost.labor_rate_source, estimated_minutes=cost.estimated_minutes,
        labor_cost_estimated=cost.labor_cost_estimated, real_travel_minutes=cost.real_travel_minutes,
        real_service_minutes=cost.real_service_minutes, labor_cost_real=cost.labor_cost_real,
        total_cost_estimated=total_est, margin_estimated=margin_est,
        margin_estimated_pct=round(margin_est / sale * 100, 1) if margin_est is not None and sale else None,
        total_cost_real=total_real, margin_real=round(sale - total_real, 2) if total_real is not None else None,
    )


@admin_router.post("/orders/{order_id}/consume", response_model=list[MovementOut], status_code=status.HTTP_201_CREATED)
async def consume_order(
    order_id: UUID,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresInventoryRepository = Depends(get_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
    pets_repo: PostgresPetRepository = Depends(get_pets_repo),
    orders_repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> list[MovementOut]:
    """
    Registra el consumo de una orden terminada (si no se registró solo, p. ej. órdenes anteriores al
    inventario). 409 `CONSUMPTION_ALREADY_REGISTERED` si ya está.
    """
    order = await _load_order(orders_repo, order_id)
    movements = await OrderConsumption(repo=repo, store_repo=store_repo, pets_repo=pets_repo).register(
        order, actor_id=current.id,
    )
    supplies = await repo.get_supplies(list({m.supply_id for m in movements}))
    return [_movement_out(m, supplies.get(m.supply_id)) for m in movements]
