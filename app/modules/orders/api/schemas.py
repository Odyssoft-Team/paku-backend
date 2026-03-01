from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.orders.domain.order import OrderStatus


class CreateOrderIn(BaseModel):
    cart_id: UUID
    address_id: Optional[UUID] = None


class UpdateStatusIn(BaseModel):
    status: OrderStatus


class PatchOrderIn(BaseModel):
    status: Optional[OrderStatus] = None


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
    # Campos de asignación (null hasta que el admin asigne)
    ally_id: Optional[UUID] = None
    scheduled_at: Optional[datetime] = None
    hold_id: Optional[UUID] = None


# ------------------------------------------------------------------
# Admin — asignación
# ------------------------------------------------------------------

class AssignOrderIn(BaseModel):
    ally_id: UUID
    scheduled_at: datetime   # ISO-8601, ej: "2026-03-07T16:00:00Z"
    notes: Optional[str] = None


class AssignmentOut(BaseModel):
    id: UUID
    order_id: UUID
    ally_id: UUID
    scheduled_at: datetime
    assigned_by: UUID
    notes: Optional[str] = None
    created_at: datetime
    # Orden actualizada con los nuevos datos
    order: OrderOut
