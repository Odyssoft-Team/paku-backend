from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CodeLabelOut(BaseModel):
    code: str
    label: str


class CampaignConfigOut(BaseModel):
    audiences: list[CodeLabelOut]
    benefits: list[CodeLabelOut]
    channels: list[CodeLabelOut]
    states: list[CodeLabelOut]


class CampaignIn(BaseModel):
    code: str = Field(min_length=1, max_length=30, description="Cupón; se guarda en mayúsculas y es único")
    name: str = Field(min_length=1, max_length=200)
    objective: Optional[str] = None
    audience: str = Field(description="Segmento de Clientes, todos, primera_compra o cumpleanos")
    benefit_type: Literal["percent", "amount", "free_addon"]
    value: float = Field(default=0, ge=0, description="% (percent) o S/ (amount)")
    addon_code: Optional[str] = Field(default=None, description="free_addon: código del adicional (ADD_…)")
    channels: list[Literal["push", "whatsapp", "email"]] = Field(default_factory=list)
    starts_on: date
    ends_on: Optional[date] = None
    status: Literal["draft", "active", "paused", "ended"] = "draft"
    automatic: bool = Field(default=False, description="True: se aplica sola; False: el cliente escribe el cupón")
    max_uses_per_customer: Optional[int] = Field(default=1, ge=1, description="null = sin límite")
    max_total_uses: Optional[int] = Field(default=None, ge=1, description="null = sin tope")


class CampaignUpdateIn(BaseModel):
    """Solo las claves enviadas."""
    code: Optional[str] = Field(default=None, min_length=1, max_length=30)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    objective: Optional[str] = None
    audience: Optional[str] = None
    benefit_type: Optional[Literal["percent", "amount", "free_addon"]] = None
    value: Optional[float] = Field(default=None, ge=0)
    addon_code: Optional[str] = None
    channels: Optional[list[Literal["push", "whatsapp", "email"]]] = None
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    status: Optional[Literal["draft", "active", "paused", "ended"]] = None
    automatic: Optional[bool] = None
    max_uses_per_customer: Optional[int] = Field(default=None, ge=1)
    max_total_uses: Optional[int] = Field(default=None, ge=1)


class CampaignOut(BaseModel):
    id: UUID
    code: str
    name: str
    objective: Optional[str] = None
    audience: str
    audience_label: str
    benefit_type: str
    benefit_label: str = Field(description="Texto del beneficio: «10 % de descuento», «S/ 15 de descuento»…")
    value: float
    addon_code: Optional[str] = None
    channels: list[str]
    starts_on: date
    ends_on: Optional[date] = None
    status: str = Field(description="Lo que puso el admin: draft | active | paused | ended")
    state: str = Field(description="Lo que se muestra: borrador | programada | activa | pausada | finalizada")
    automatic: bool
    max_uses_per_customer: Optional[int] = None
    max_total_uses: Optional[int] = None
    uses: int = Field(description="Usos vigentes (cuentan para los topes)")
    paid_uses: int = Field(description="Usos en órdenes pagadas")
    discount_given: float = Field(description="Descuento otorgado en órdenes pagadas")
    sales: float = Field(description="Ventas (neto) de las órdenes pagadas con la campaña")
    audience_size: Optional[int] = Field(default=None, description="Clientes que hoy están en el público")
    created_at: datetime
    updated_at: datetime


class CampaignQuoteIn(BaseModel):
    cart_id: UUID
    code: Optional[str] = Field(default=None, description="Cupón que escribió el cliente (opcional)")


class CampaignQuoteOut(BaseModel):
    subtotal: float
    discount: float
    total: float
    campaign_id: Optional[UUID] = None
    campaign_name: Optional[str] = None
    benefit_label: Optional[str] = None
    automatic: Optional[bool] = None
