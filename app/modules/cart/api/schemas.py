from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.cart.domain.cart import CartItemKind, CartStatus


# [TECH]
# Output DTO serializing CartSession for API responses.
#
# [NATURAL/BUSINESS]
# Representación del carrito que devuelve la API.
class CartOut(BaseModel):
    id: UUID
    user_id: UUID
    status: CartStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


# [TECH]
# Input DTO for adding items to cart with validation.
#
# [NATURAL/BUSINESS]
# Datos para agregar un producto al carrito.
class CartItemIn(BaseModel):
    kind: CartItemKind
    ref_id: Union[UUID, str]
    name: Optional[str] = None
    qty: int = Field(1, ge=1)
    unit_price: Optional[float] = None
    meta: Optional[dict[str, Any]] = None


# [TECH]
# Input DTO for batch adding items to cart.
#
# [NATURAL/BUSINESS]
# Datos para agregar múltiples items al carrito de una vez.
class CartItemsBatchIn(BaseModel):
    items: list[CartItemIn] = Field(..., min_length=1, description="Lista de items a agregar (mínimo 1)")


# [TECH]
# Output DTO serializing CartItem for API responses.
#
# [NATURAL/BUSINESS]
# Representación de item del carrito que devuelve la API.
class CartItemOut(BaseModel):
    id: UUID
    cart_id: UUID
    kind: CartItemKind
    ref_id: Union[UUID, str]
    name: Optional[str] = None
    qty: int
    unit_price: Optional[float] = None
    meta: Optional[dict[str, Any]] = None


# [TECH]
# Composite DTO returning cart with its items.
#
# [NATURAL/BUSINESS]
# Carrito completo con todos sus productos.
class CartWithItemsOut(BaseModel):
    cart: CartOut
    items: list[CartItemOut]


# [TECH]
# Output DTO for checkout with totals and items.
#
# [NATURAL/BUSINESS]
# Resumen del pedido tras finalizar el carrito.
class CheckoutOut(BaseModel):
    cart_id: UUID
    status: str
    total: float
    currency: str
    items: list[CartItemOut]


class CartValidationOut(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list, description="Lista de errores que bloquean el checkout")
    warnings: list[str] = Field(default_factory=list, description="Lista de advertencias no bloqueantes")
    total: float = Field(description="Total calculado del carrito")
    currency: str = Field(default="PEN", description="Moneda del total")
