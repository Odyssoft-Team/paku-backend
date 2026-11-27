from __future__ import annotations

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.expenses.domain.expenses import MONTHLY, Expense, Vehicle
from app.modules.expenses.infra.models import ExpenseModel, VehicleModel, utcnow


def _vehicle(m: VehicleModel) -> Vehicle:
    return Vehicle(id=m.id, name=m.name, plate=m.plate, brand=m.brand, model=m.model, year=m.year,
                   is_active=m.is_active, notes=m.notes, created_at=m.created_at)


def _expense(m: ExpenseModel) -> Expense:
    return Expense(
        id=m.id, kind=m.kind, category=m.category, description=m.description, start_date=m.start_date,
        end_date=m.end_date, total_paid=float(m.total_paid), igv_included=m.igv_included, amount=float(m.amount),
        vehicle_id=m.vehicle_id, supplier=m.supplier, document=m.document, notes=m.notes, created_at=m.created_at,
        created_by=m.created_by, voided_at=m.voided_at, void_reason=m.void_reason)


class PostgresExpensesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------- Vehículos ----------

    async def list_vehicles(self) -> list[Vehicle]:
        rows = (await self._session.execute(select(VehicleModel).order_by(VehicleModel.name))).scalars().all()
        return [_vehicle(m) for m in rows]

    async def get_vehicle(self, vehicle_id: UUID) -> Optional[Vehicle]:
        m = await self._session.get(VehicleModel, vehicle_id)
        return _vehicle(m) if m else None

    async def plate_taken(self, plate: str, *, exclude_id: Optional[UUID] = None) -> bool:
        stmt = select(VehicleModel.id).where(VehicleModel.plate == plate)
        if exclude_id is not None:
            stmt = stmt.where(VehicleModel.id != exclude_id)
        return (await self._session.execute(stmt)).first() is not None

    async def save_vehicle(self, vehicle_id: Optional[UUID], fields: dict) -> Vehicle:
        m = await self._session.get(VehicleModel, vehicle_id) if vehicle_id else VehicleModel()
        if m is None:
            raise ValueError("vehicle_not_found")
        for k, v in fields.items():
            setattr(m, k, v)
        m.updated_at = utcnow()
        self._session.add(m)
        await self._session.commit()
        await self._session.refresh(m)
        return _vehicle(m)

    # ---------- Gastos ----------

    async def get_expense(self, expense_id: UUID) -> Optional[Expense]:
        m = await self._session.get(ExpenseModel, expense_id)
        return _expense(m) if m else None

    async def save_expense(self, expense_id: Optional[UUID], fields: dict) -> Expense:
        m = await self._session.get(ExpenseModel, expense_id) if expense_id else ExpenseModel()
        if m is None:
            raise ValueError("expense_not_found")
        for k, v in fields.items():
            setattr(m, k, v)
        m.updated_at = utcnow()
        self._session.add(m)
        await self._session.commit()
        await self._session.refresh(m)
        return _expense(m)

    async def list_expenses(self, *, date_from: Optional[date] = None, date_to: Optional[date] = None,
                            include_voided: bool = False, category: Optional[str] = None,
                            vehicle_id: Optional[UUID] = None) -> list[Expense]:
        """Gastos que pueden afectar [date_from, date_to]: los que empiezan hasta date_to y, si son únicos o anuales,
        desde un año antes de date_from (el caso fino lo resuelve `allocation`). Sin fechas, todos."""
        stmt = select(ExpenseModel).order_by(ExpenseModel.start_date.desc(), ExpenseModel.created_at.desc())
        if date_to is not None:
            stmt = stmt.where(ExpenseModel.start_date <= date_to)
        if date_from is not None:
            stmt = stmt.where(or_(ExpenseModel.kind == MONTHLY,
                                  ExpenseModel.start_date >= date_from - timedelta(days=370)))
            stmt = stmt.where(or_(ExpenseModel.end_date.is_(None), ExpenseModel.end_date >= date_from))
        if not include_voided:
            stmt = stmt.where(ExpenseModel.voided_at.is_(None))
        if category:
            stmt = stmt.where(ExpenseModel.category == category)
        if vehicle_id is not None:
            stmt = stmt.where(ExpenseModel.vehicle_id == vehicle_id)
        return [_expense(m) for m in (await self._session.execute(stmt)).scalars().all()]
