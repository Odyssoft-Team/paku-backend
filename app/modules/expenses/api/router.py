"""Gastos operativos y vehículos (feature 0026). Solo admin."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.modules.expenses.api.schemas import (
    CodeLabelOut,
    ExpenseIn,
    ExpenseListOut,
    ExpenseOut,
    ExpensesConfigOut,
    VehicleIn,
    VehicleOut,
    VoidIn,
)
from app.modules.expenses.app.use_cases import ListExpenses, SaveExpense, SaveVehicle, VoidExpense
from app.modules.expenses.domain.expenses import CATEGORIES, KINDS, Expense, coverage_end
from app.modules.expenses.infra.postgres_expenses_repository import PostgresExpensesRepository

admin_router = APIRouter(tags=["expenses-admin"])
admin_only = require_roles("admin")


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresExpensesRepository:
    return PostgresExpensesRepository(session=session)


def igv_reader(session: AsyncSession = Depends(get_async_session)):
    from app.modules.general_settings.app.use_cases import get_setting
    from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository

    async def read() -> float:
        return float(await get_setting(PostgresSettingsRepository(session=session), "igv_percent") or 0)

    return read


def expense_out(e: Expense, vehicles: dict, in_period: Optional[float] = None) -> ExpenseOut:
    label, group = CATEGORIES.get(e.category, (e.category, "Otros"))
    v = vehicles.get(e.vehicle_id)
    return ExpenseOut(
        id=e.id, kind=e.kind, kind_label=KINDS.get(e.kind, e.kind), category=e.category, category_label=label,
        category_group=group, description=e.description, start_date=e.start_date, end_date=e.end_date,
        coverage_end=coverage_end(e), total_paid=e.total_paid, igv_included=e.igv_included, amount=e.amount,
        in_period=in_period, vehicle_id=e.vehicle_id, vehicle_name=v.name if v else None, supplier=e.supplier,
        document=e.document, notes=e.notes, created_at=e.created_at, voided_at=e.voided_at, void_reason=e.void_reason)


@admin_router.get("/expenses/config", response_model=ExpensesConfigOut)
async def expenses_config(_: CurrentUser = Depends(admin_only)) -> ExpensesConfigOut:
    return ExpensesConfigOut(
        kinds=[CodeLabelOut(code=k, label=v) for k, v in KINDS.items()],
        categories=[CodeLabelOut(code=k, label=lbl, group=g) for k, (lbl, g) in CATEGORIES.items()])


@admin_router.get("/expenses", response_model=ExpenseListOut)
async def list_expenses(
    date_from: Optional[date] = Query(None, description="Con date_to: solo los que aportan al período, con su parte."),
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    vehicle_id: Optional[UUID] = None,
    include_voided: bool = False,
    _: CurrentUser = Depends(admin_only),
    repo: PostgresExpensesRepository = Depends(get_repo),
) -> ExpenseListOut:
    """Gastos (más recientes primero). Con período, `in_period` es lo que cada uno aporta (sin IGV; mensual y anual se
    reparten por días) y `total_in_period` la suma; así cuadra con «Gastos operativos» del P&L."""
    if (date_from is None) != (date_to is None) or (date_from and date_to and date_from > date_to):
        raise HTTPException(status_code=422, detail={"code": "PERIOD_INVALID",
                                                      "message": "Indica desde y hasta (desde ≤ hasta)."})
    rows = await ListExpenses(repo=repo).execute(date_from=date_from, date_to=date_to, include_voided=include_voided,
                                                 category=category, vehicle_id=vehicle_id)
    vehicles = {v.id: v for v in await repo.list_vehicles()}
    by_cat: dict[str, float] = {}
    for r in rows:
        if r.in_period and not r.expense.is_voided:
            by_cat[r.expense.category] = round(by_cat.get(r.expense.category, 0.0) + r.in_period, 2)
    return ExpenseListOut(
        items=[expense_out(r.expense, vehicles, r.in_period) for r in rows],
        total_in_period=round(sum(by_cat.values()), 2) if date_from else None,
        by_category=[CodeLabelOut(code=c, label=CATEGORIES.get(c, (c, ""))[0]) for c in by_cat],
        by_category_amount=by_cat)


@admin_router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseIn, current: CurrentUser = Depends(admin_only),
                         repo: PostgresExpensesRepository = Depends(get_repo), igv=Depends(igv_reader)) -> ExpenseOut:
    """422 `EXPENSE_INVALID` con `field`. El monto sin IGV se calcula con el IGV de Parámetros generales."""
    fields = payload.model_dump()
    if fields["igv_included"] is None:
        fields["igv_included"] = False
    e = await SaveExpense(repo=repo, igv_percent=igv).execute(None, fields=fields, actor_id=current.id)
    return expense_out(e, {v.id: v for v in await repo.list_vehicles()})


@admin_router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
async def update_expense(expense_id: UUID, payload: ExpenseIn, current: CurrentUser = Depends(admin_only),
                         repo: PostgresExpensesRepository = Depends(get_repo), igv=Depends(igv_reader)) -> ExpenseOut:
    """Solo cambia lo enviado. 409 `EXPENSE_VOIDED` si está anulado. Para dejar de pagar un gasto mensual: `end_date`."""
    fields = {k: getattr(payload, k) for k in payload.model_fields_set}
    e = await SaveExpense(repo=repo, igv_percent=igv).execute(expense_id, fields=fields, actor_id=current.id)
    return expense_out(e, {v.id: v for v in await repo.list_vehicles()})


@admin_router.post("/expenses/{expense_id}/void", response_model=ExpenseOut)
async def void_expense(expense_id: UUID, payload: VoidIn, current: CurrentUser = Depends(admin_only),
                       repo: PostgresExpensesRepository = Depends(get_repo)) -> ExpenseOut:
    """Anula con motivo: deja de contar en el P&L; queda en el historial."""
    e = await VoidExpense(repo=repo).execute(expense_id, reason=payload.reason, actor_id=current.id)
    return expense_out(e, {v.id: v for v in await repo.list_vehicles()})


@admin_router.get("/vehicles", response_model=list[VehicleOut])
async def list_vehicles(_: CurrentUser = Depends(admin_only),
                        repo: PostgresExpensesRepository = Depends(get_repo)) -> list[VehicleOut]:
    return [VehicleOut(**v.__dict__) for v in await repo.list_vehicles()]


@admin_router.post("/vehicles", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
async def create_vehicle(payload: VehicleIn, _: CurrentUser = Depends(admin_only),
                         repo: PostgresExpensesRepository = Depends(get_repo)) -> VehicleOut:
    """409 `PLATE_EXISTS`; 422 `EXPENSE_INVALID` (nombre o año)."""
    fields = payload.model_dump()
    fields["is_active"] = True if fields["is_active"] is None else fields["is_active"]
    return VehicleOut(**(await SaveVehicle(repo=repo).execute(None, fields=fields)).__dict__)


@admin_router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(vehicle_id: UUID, payload: VehicleIn, _: CurrentUser = Depends(admin_only),
                         repo: PostgresExpensesRepository = Depends(get_repo)) -> VehicleOut:
    fields = {k: getattr(payload, k) for k in payload.model_fields_set}
    return VehicleOut(**(await SaveVehicle(repo=repo).execute(vehicle_id, fields=fields)).__dict__)
