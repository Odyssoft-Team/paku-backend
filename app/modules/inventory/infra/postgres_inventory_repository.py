from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.domain.inventory import Movement, Recipe, RecipeCell, RecipeLine, Supply
from app.modules.inventory.infra.models import (
    MovementModel,
    RecipeCellModel,
    RecipeLineModel,
    RecipeModel,
    SupplyModel,
    utcnow,
)


def _f(value) -> float:
    return float(value) if value is not None else 0.0


class PostgresInventoryRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Insumos
    # ------------------------------------------------------------------

    @staticmethod
    def _to_supply(m: SupplyModel) -> Supply:
        return Supply(
            id=m.id, sku=m.sku, name=m.name, category=m.category, purchase_unit=m.purchase_unit,
            purchase_content=_f(m.purchase_content), consumption_unit=m.consumption_unit,
            purchase_cost=_f(m.purchase_cost), min_stock=_f(m.min_stock), tracks_lot=bool(m.tracks_lot),
            tracks_expiry=bool(m.tracks_expiry), is_active=bool(m.is_active),
            created_at=m.created_at, updated_at=m.updated_at,
        )

    async def list_supplies(self, *, include_inactive: bool = True) -> list[Supply]:
        stmt = select(SupplyModel).order_by(SupplyModel.sku)
        if not include_inactive:
            stmt = stmt.where(SupplyModel.is_active.is_(True))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_supply(r) for r in rows]

    async def get_supply(self, supply_id: UUID) -> Optional[Supply]:
        m = await self._session.get(SupplyModel, supply_id)
        return self._to_supply(m) if m else None

    async def get_supplies(self, ids: list[UUID]) -> dict[UUID, Supply]:
        if not ids:
            return {}
        rows = (await self._session.execute(select(SupplyModel).where(SupplyModel.id.in_(ids)))).scalars().all()
        return {r.id: self._to_supply(r) for r in rows}

    async def list_skus(self) -> list[str]:
        return list((await self._session.execute(select(SupplyModel.sku))).scalars().all())

    async def create_supply(self, *, sku: str, fields: dict) -> Supply:
        now = utcnow()
        m = SupplyModel(sku=sku, created_at=now, updated_at=now, is_active=True, **fields)
        self._session.add(m)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ValueError("sku_taken")
        await self._session.refresh(m)
        return self._to_supply(m)

    async def update_supply(self, supply_id: UUID, patch: dict) -> Supply:
        m = await self._session.get(SupplyModel, supply_id)
        if m is None:
            raise ValueError("supply_not_found")
        for key, value in patch.items():
            setattr(m, key, value)
        m.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(m)
        return self._to_supply(m)

    async def stock_by_supply(self) -> dict[UUID, float]:
        """Stock de cada insumo = suma de sus movimientos."""
        stmt = select(MovementModel.supply_id, func.sum(MovementModel.quantity)).group_by(MovementModel.supply_id)
        return {sid: _f(total) for sid, total in (await self._session.execute(stmt)).all()}

    # ------------------------------------------------------------------
    # Movimientos
    # ------------------------------------------------------------------

    @staticmethod
    def _to_movement(m: MovementModel, created_by_name: Optional[str] = None) -> Movement:
        return Movement(
            id=m.id, seq=m.seq, occurred_on=m.occurred_on, type=m.type, supply_id=m.supply_id,
            quantity=_f(m.quantity), unit_cost=_f(m.unit_cost), location=m.location, cost_center=m.cost_center,
            reason=m.reason, created_at=m.created_at, order_id=m.order_id, recipe_id=m.recipe_id,
            recipe_cell_id=m.recipe_cell_id, lot=m.lot,
            expires_on=m.expires_on, created_by=m.created_by, created_by_name=created_by_name,
        )

    async def add_movements(self, movements: list[dict], *, commit: bool = True) -> list[Movement]:
        """Inserta movimientos (dicts con las columnas). `commit=False` deja la transacción abierta."""
        now = utcnow()
        models = [MovementModel(created_at=now, **m) for m in movements]
        self._session.add_all(models)
        await self._session.flush()
        if commit:
            await self._session.commit()
        for m in models:
            await self._session.refresh(m)
        return [self._to_movement(m) for m in models]

    @staticmethod
    def _with_author():
        """SELECT de movimientos con el nombre de quien lo registró (null = sistema)."""
        from app.modules.iam.infra.models import UserModel

        name = func.concat(UserModel.first_name, " ", UserModel.last_name)
        return select(MovementModel, name).outerjoin(UserModel, UserModel.id == MovementModel.created_by)

    def _rows_to_movements(self, rows) -> list[Movement]:
        return [self._to_movement(m, ((n or "").strip() or None) if m.created_by else None) for m, n in rows]

    async def get_movement(self, movement_id: UUID) -> Optional[Movement]:
        rows = (await self._session.execute(self._with_author().where(MovementModel.id == movement_id))).all()
        found = self._rows_to_movements(rows)
        return found[0] if found else None

    async def list_movements(
        self,
        *,
        type: Optional[str] = None,
        supply_id: Optional[UUID] = None,
        order_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 500,
    ) -> list[Movement]:
        """Del más reciente al más antiguo (fecha y número)."""
        stmt = (
            self._with_author()
            .order_by(desc(MovementModel.occurred_on), desc(MovementModel.seq))
            .limit(limit)
        )
        if type:
            stmt = stmt.where(MovementModel.type == type)
        if supply_id:
            stmt = stmt.where(MovementModel.supply_id == supply_id)
        if order_id:
            stmt = stmt.where(MovementModel.order_id == order_id)
        if date_from:
            stmt = stmt.where(MovementModel.occurred_on >= date_from)
        if date_to:
            stmt = stmt.where(MovementModel.occurred_on <= date_to)
        return self._rows_to_movements((await self._session.execute(stmt)).all())

    async def has_order_consumption(self, order_id: UUID) -> bool:
        stmt = select(MovementModel.id).where(
            MovementModel.order_id == order_id, MovementModel.type == "consumption"
        ).limit(1)
        return (await self._session.execute(stmt)).first() is not None

    async def consumption_totals(self, *, date_from: Optional[date], date_to: Optional[date]) -> tuple[float, int]:
        """Costo de los consumos por servicio del período y cuántas órdenes lo generaron."""
        stmt = select(
            func.coalesce(func.sum(-MovementModel.quantity * MovementModel.unit_cost), 0),
            func.count(func.distinct(MovementModel.order_id)),
        ).where(MovementModel.type == "consumption")
        if date_from:
            stmt = stmt.where(MovementModel.occurred_on >= date_from)
        if date_to:
            stmt = stmt.where(MovementModel.occurred_on <= date_to)
        cost, orders = (await self._session.execute(stmt)).one()
        return _f(cost), int(orders or 0)

    # ------------------------------------------------------------------
    # Recetas
    # ------------------------------------------------------------------

    async def _cells_for(self, recipe_ids: list[UUID]) -> dict[UUID, list[RecipeCell]]:
        if not recipe_ids:
            return {}
        cells = (await self._session.execute(
            select(RecipeCellModel).where(RecipeCellModel.recipe_id.in_(recipe_ids))
            .order_by(RecipeCellModel.breed_category, RecipeCellModel.weight_min)
        )).scalars().all()
        lines = (await self._session.execute(
            select(RecipeLineModel).where(RecipeLineModel.cell_id.in_([c.id for c in cells])).order_by(RecipeLineModel.id)
        )).scalars().all() if cells else []
        by_cell: dict[UUID, list[RecipeLine]] = {}
        for line in lines:
            by_cell.setdefault(line.cell_id, []).append(RecipeLine(supply_id=line.supply_id, quantity=_f(line.quantity)))
        out: dict[UUID, list[RecipeCell]] = {}
        for c in cells:
            out.setdefault(c.recipe_id, []).append(RecipeCell(
                id=c.id, breed_category=c.breed_category, weight_min=float(c.weight_min),
                weight_max=float(c.weight_max) if c.weight_max is not None else None,
                labor_minutes=_f(c.labor_minutes), lines=by_cell.get(c.id, []),
            ))
        return out

    async def _to_recipes(self, models: list[RecipeModel]) -> list[Recipe]:
        cells = await self._cells_for([m.id for m in models])
        return [
            Recipe(
                id=m.id, target_type=m.target_type, target_id=m.target_id, version=m.version,
                is_current=bool(m.is_current), cells=cells.get(m.id, []), created_at=m.created_at,
                created_by=m.created_by,
            )
            for m in models
        ]

    async def list_recipes(self, *, current_only: bool = True, target_id: Optional[UUID] = None) -> list[Recipe]:
        """Recetas (vigentes o todas las versiones), de la versión más nueva a la más vieja por target."""
        stmt = select(RecipeModel).order_by(RecipeModel.target_id, desc(RecipeModel.version))
        if current_only:
            stmt = stmt.where(RecipeModel.is_current.is_(True))
        if target_id is not None:
            stmt = stmt.where(RecipeModel.target_id == target_id)
        return await self._to_recipes(list((await self._session.execute(stmt)).scalars().all()))

    async def current_recipes_for(self, target_ids: list[UUID]) -> dict[UUID, Recipe]:
        if not target_ids:
            return {}
        stmt = select(RecipeModel).where(RecipeModel.target_id.in_(target_ids), RecipeModel.is_current.is_(True))
        return {r.target_id: r for r in await self._to_recipes(list((await self._session.execute(stmt)).scalars().all()))}

    async def get_recipes(self, ids: list[UUID]) -> dict[UUID, Recipe]:
        if not ids:
            return {}
        rows = (await self._session.execute(select(RecipeModel).where(RecipeModel.id.in_(ids)))).scalars().all()
        return {r.id: r for r in await self._to_recipes(list(rows))}

    async def save_recipe_version(
        self,
        *,
        target_type: str,
        target_id: UUID,
        version: int,
        cells: list[RecipeCell],
        created_by: Optional[UUID],
        replaces: Optional[UUID] = None,
    ) -> Recipe:
        """Crea una versión (vigente) de la tabla. `replaces`: versión anterior, que deja de estar vigente."""
        try:
            if replaces is not None:
                await self._session.execute(
                    update(RecipeModel).where(RecipeModel.id == replaces).values(is_current=False)
                )
            m = RecipeModel(target_type=target_type, target_id=target_id, version=version, is_current=True,
                            created_by=created_by, created_at=utcnow())
            self._session.add(m)
            await self._session.flush()  # la versión repetida (otra persona guardó antes) falla aquí
            for cell in cells:
                cm = RecipeCellModel(recipe_id=m.id, breed_category=cell.breed_category, weight_min=cell.weight_min,
                                     weight_max=cell.weight_max, labor_minutes=Decimal(str(cell.labor_minutes)))
                self._session.add(cm)
                await self._session.flush()
                self._session.add_all([
                    RecipeLineModel(cell_id=cm.id, supply_id=line.supply_id, quantity=Decimal(str(line.quantity)))
                    for line in cell.lines
                ])
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ValueError("recipe_version_taken")
        await self._session.refresh(m)
        return (await self._to_recipes([m]))[0]
