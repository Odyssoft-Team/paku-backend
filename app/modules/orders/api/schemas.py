from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.orders.domain.order import OrderStatus


class CreateOrderIn(BaseModel):
    cart_id: UUID


class UpdateStatusIn(BaseModel):
    status: OrderStatus


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
