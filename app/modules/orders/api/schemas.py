from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.orders.domain.order import OrderStatus


# [TECH]
# Input DTO for order creation from existing cart.
#
# [NATURAL/BUSINESS]
# Datos para crear un pedido desde el carrito.
class CreateOrderIn(BaseModel):
    cart_id: UUID
    address_id: UUID


# [TECH]
# Input DTO for order status updates by admin/ally.
#
# [NATURAL/BUSINESS]
# Nuevo estado para actualizar un pedido existente.
class UpdateStatusIn(BaseModel):
    status: OrderStatus


# [TECH]
# Input DTO for PATCH /orders/{id} - partial updates.
#
# [NATURAL/BUSINESS]
# Campos opcionales para actualizar un pedido.
class PatchOrderIn(BaseModel):
    status: Optional[OrderStatus] = None


# [TECH]
# Output DTO serializing Order entity for API responses.
#
# [NATURAL/BUSINESS]
# Representación completa de pedido que devuelve la API.
class OrderOut(BaseModel):
    id: UUID
    user_id: UUID
    status: OrderStatus
    items_snapshot: Any
    total_snapshot: float
    currency: str
    delivery_address_snapshot: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
