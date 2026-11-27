"""Gastos operativos y vehículos (feature 0026)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Optional
from uuid import UUID

from fastapi import HTTPException

from app.core.timezone import today_lima
from app.modules.expenses.domain.expenses import (
    Expense,
    ExpenseInvalid,
    Vehicle,
    allocation,
    net_amount,
    validate,
)
from app.modules.expenses.infra.models import utcnow


def _invalid(field: str, message: str) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": "EXPENSE_INVALID", "field": field, "message": message})


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"{what} no encontrado."})


def _clean(v: Optional[str]) -> Optional[str]:
    v = (v or "").strip()
    return v or None


# ---------- Vehículos ----------

@dataclass
class SaveVehicle:
    repo: Any

    async def execute(self, vehicle_id: Optional[UUID], *, fields: dict) -> Vehicle:
        """Crea (vehicle_id None) o edita. `fields`: solo lo enviado al editar."""
        data = dict(fields)
        if "name" in data or vehicle_id is None:
            data["name"] = _clean(data.get("name"))
            if not data["name"]:
                raise _invalid("name", "Ponle un nombre al vehículo (p. ej. «Paku 01»).")
        if "plate" in data:
            data["plate"] = _clean(data["plate"])
            data["plate"] = data["plate"].upper() if data["plate"] else None
            if data["plate"] and await self.repo.plate_taken(data["plate"], exclude_id=vehicle_id):
                raise HTTPException(status_code=409, detail={"code": "PLATE_EXISTS",
                                                             "message": "Ya hay un vehículo con esa placa."})
        for k in ("brand", "model", "notes"):
            if k in data:
                data[k] = _clean(data[k])
        if data.get("year") is not None and not 1950 <= int(data["year"]) <= today_lima().year + 1:
            raise _invalid("year", "Año no válido.")
        if vehicle_id is not None and await self.repo.get_vehicle(vehicle_id) is None:
            raise _not_found("Vehículo")
        return await self.repo.save_vehicle(vehicle_id, data)


# ---------- Gastos ----------

@dataclass
class SaveExpense:
    """Crea o edita un gasto. El monto sin IGV se calcula aquí con el IGV de Parámetros generales."""
    repo: Any
    igv_percent: Callable          # async () -> float

    async def execute(self, expense_id: Optional[UUID], *, fields: dict, actor_id: UUID) -> Expense:
        current = await self.repo.get_expense(expense_id) if expense_id else None
        if expense_id is not None:
            if current is None:
                raise _not_found("Gasto")
            if current.is_voided:
                raise HTTPException(status_code=409, detail={"code": "EXPENSE_VOIDED",
                                                             "message": "El gasto está anulado: no se edita."})
        merged = {
            k: fields[k] if k in fields else (getattr(current, k) if current else None)
            for k in ("kind", "category", "description", "start_date", "end_date", "total_paid", "igv_included",
                      "vehicle_id", "supplier", "document", "notes")
        }
        if merged["kind"] != "monthly":
            merged["end_date"] = None
        try:
            validate(kind=merged["kind"], category=merged["category"], description=merged["description"],
                     start_date=merged["start_date"], end_date=merged["end_date"],
                     total_paid=float(merged["total_paid"]) if merged["total_paid"] is not None else None,
                     today=today_lima())
        except ExpenseInvalid as exc:
            raise _invalid(exc.field, exc.message) from exc
        if merged["vehicle_id"] is not None and await self.repo.get_vehicle(merged["vehicle_id"]) is None:
            raise _invalid("vehicle_id", "Vehículo no encontrado.")
        igv = float(await self.igv_percent() or 0)
        total = round(float(merged["total_paid"]), 2)
        data = {
            "kind": merged["kind"], "category": merged["category"], "description": merged["description"].strip()[:300],
            "start_date": merged["start_date"], "end_date": merged["end_date"], "total_paid": Decimal(str(total)),
            "igv_included": bool(merged["igv_included"]),
            "amount": Decimal(str(net_amount(total, bool(merged["igv_included"]), igv))),
            "vehicle_id": merged["vehicle_id"], "supplier": _clean(merged["supplier"]),
            "document": _clean(merged["document"]), "notes": _clean(merged["notes"]), "updated_by": actor_id,
        }
        if expense_id is None:
            data["created_by"] = actor_id
        return await self.repo.save_expense(expense_id, data)


@dataclass
class VoidExpense:
    repo: Any

    async def execute(self, expense_id: UUID, *, reason: str, actor_id: UUID) -> Expense:
        current = await self.repo.get_expense(expense_id)
        if current is None:
            raise _not_found("Gasto")
        if current.is_voided:
            raise HTTPException(status_code=409, detail={"code": "EXPENSE_VOIDED", "message": "Ya está anulado."})
        if len((reason or "").strip()) < 3:
            raise _invalid("reason", "Indica por qué se anula.")
        return await self.repo.save_expense(expense_id, {
            "voided_at": utcnow(), "voided_by": actor_id, "void_reason": reason.strip()[:500]})


@dataclass(frozen=True)
class ExpenseRow:
    expense: Expense
    in_period: Optional[float]     # lo que aporta al período consultado (sin IGV); None sin período


@dataclass
class ListExpenses:
    repo: Any

    async def execute(self, *, date_from: Optional[date] = None, date_to: Optional[date] = None,
                      include_voided: bool = False, category: Optional[str] = None,
                      vehicle_id: Optional[UUID] = None) -> list[ExpenseRow]:
        """Con período: solo los que aportan algo a él (hasta hoy), con su parte."""
        expenses = await self.repo.list_expenses(date_from=date_from, date_to=date_to, include_voided=include_voided,
                                                 category=category, vehicle_id=vehicle_id)
        if date_from is None or date_to is None:
            return [ExpenseRow(e, None) for e in expenses]
        cut = min(date_to, today_lima())
        rows = [ExpenseRow(e, allocation(e, date_from, cut)) for e in expenses]
        return [r for r in rows if r.in_period or r.expense.is_voided]


def expense_allocations(expenses: list[Expense], start: date, cut: date) -> list[tuple[Expense, float]]:
    """(gasto, parte del período) de los que aportan algo; para el P&L."""
    out = [(e, allocation(e, start, cut)) for e in expenses]
    return [(e, a) for e, a in out if a]
