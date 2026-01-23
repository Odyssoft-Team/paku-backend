from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.cart.domain.cart import CartItemKind, CartStatus


class CartOut(BaseModel):
    id: UUID
    user_id: UUID
    status: CartStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class CartItemIn(BaseModel):
    kind: CartItemKind
    ref_id: Union[UUID, str]
    name: Optional[str] = None
    qty: int = Field(1, ge=1)
    unit_price: Optional[float] = None
    meta: Optional[dict[str, Any]] = None


class CartItemOut(BaseModel):
    id: UUID
    cart_id: UUID
    kind: CartItemKind
    ref_id: Union[UUID, str]
    name: Optional[str] = None
    qty: int
    unit_price: Optional[float] = None
    meta: Optional[dict[str, Any]] = None


class CartWithItemsOut(BaseModel):
    cart: CartOut
    items: list[CartItemOut]


class CheckoutOut(BaseModel):
    cart_id: UUID
    status: str
    total: float
    currency: str
    items: list[CartItemOut]
