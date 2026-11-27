from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

ExpenseKind = Literal["one_time", "monthly", "annual"]


class CodeLabelOut(BaseModel):
    code: str
    label: str
    group: Optional[str] = None


class ExpensesConfigOut(BaseModel):
    kinds: list[CodeLabelOut]
    categories: list[CodeLabelOut]


class VehicleOut(BaseModel):
    id: UUID
    name: str
    plate: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime


class VehicleIn(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="Obligatorio al crear (p. ej. «Paku 01»).")
    plate: Optional[str] = Field(None, max_length=20)
    brand: Optional[str] = Field(None, max_length=60)
    model: Optional[str] = Field(None, max_length=60)
    year: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)


class ExpenseOut(BaseModel):
    id: UUID
    kind: ExpenseKind
    kind_label: str
    category: str
    category_label: str
    category_group: str
    description: str
    start_date: date
    end_date: Optional[date] = None
    coverage_end: Optional[date] = Field(None, description="Hasta cuándo afecta (anual: 12 meses; mensual sin fin: null).")
    total_paid: float
    igv_included: bool
    amount: float = Field(..., description="Sin IGV. En un gasto mensual, por mes; en único y anual, el total.")
    in_period: Optional[float] = Field(None, description="Lo que aporta al período consultado (sin IGV).")
    vehicle_id: Optional[UUID] = None
    vehicle_name: Optional[str] = None
    supplier: Optional[str] = None
    document: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None


class ExpenseIn(BaseModel):
    """Al crear van todos los obligatorios; al editar, solo lo que cambia."""
    kind: Optional[ExpenseKind] = None
    category: Optional[str] = None
    description: Optional[str] = Field(None, max_length=300)
    start_date: Optional[date] = Field(None, description="Fecha del gasto (único) o desde cuándo rige.")
    end_date: Optional[date] = Field(None, description="Solo mensual: último día vigente (null = sigue).")
    total_paid: Optional[float] = Field(None, gt=0, description="Lo pagado, con IGV si igv_included.")
    igv_included: Optional[bool] = None
    vehicle_id: Optional[UUID] = None
    supplier: Optional[str] = Field(None, max_length=200)
    document: Optional[str] = Field(None, max_length=60)
    notes: Optional[str] = Field(None, max_length=1000)


class VoidIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class ExpenseListOut(BaseModel):
    items: list[ExpenseOut]
    total_in_period: Optional[float] = Field(None, description="Suma de in_period (sin anulados).")
    by_category: list[CodeLabelOut] = Field(default_factory=list)
    by_category_amount: dict[str, float] = Field(default_factory=dict)
