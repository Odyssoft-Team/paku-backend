from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class PeriodOut(BaseModel):
    date_from: date
    date_to: date


class MetricOut(BaseModel):
    key: str
    label: str
    unit: str = Field(description="count | money | pct | minutes")
    description: str
    value: Optional[float] = Field(default=None, description="Mes al día; null = sin datos")
    quality: str = Field(description="real | estimated | no_data")
    with_data: Optional[int] = Field(default=None, description="Órdenes medidas o estimadas…")
    total: Optional[int] = Field(default=None, description="…de cuántas (solo cifras parciales)")
    previous: Optional[float] = Field(default=None, description="Mismo corte del mes anterior")
    previous_quality: str
    delta: Optional[float] = None
    delta_pct: Optional[float] = None


class DayOutlookOut(BaseModel):
    date: date
    capacity: Optional[int] = Field(default=None, description="null: el día no tiene cupos")
    booked: Optional[int] = None
    occupancy_pct: Optional[float] = None
    scheduled: int = Field(description="Servicios solicitados (pagados o en verificación) para ese día")


class DashboardOut(BaseModel):
    cut: date
    period: PeriodOut
    previous_period: PeriodOut
    metrics: list[MetricOut]
    scheduled_rest_of_month: int = Field(description="Servicios solicitados del corte a fin de mes")
    next_days: list[DayOutlookOut]
