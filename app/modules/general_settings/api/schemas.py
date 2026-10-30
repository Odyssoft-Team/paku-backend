from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SettingFieldOut(BaseModel):
    key: str
    label: str
    type: str = Field(description="text | ruc | email | phone | time | percent | int | readonly")
    value: Any = None
    default: Any = None
    editable: bool
    help: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None


class SettingSectionOut(BaseModel):
    code: str
    title: str
    fields: list[SettingFieldOut]


class GeneralSettingsOut(BaseModel):
    values: dict[str, Any] = Field(description="Valor efectivo de cada parámetro (clave → valor)")
    sections: list[SettingSectionOut]
    updated_at: Optional[datetime] = None
    updated_by: Optional[UUID] = None


class GeneralSettingsUpdateIn(BaseModel):
    values: dict[str, Any] = Field(description="Solo las claves a cambiar; null vuelve al valor por defecto")
