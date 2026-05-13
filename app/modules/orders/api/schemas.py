from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.orders.domain.order import OrderStatus, PaymentStatus


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
    # Pago: pending hasta que el frontend confirme el cargo desde culqi-python
    payment_status: PaymentStatus = PaymentStatus.pending
    culqi_charge_id: Optional[str] = None  # chr_(test|live)_XXXXXXXXXXXXXXXX


class ConfirmPaymentIn(BaseModel):
    """
    Payload que envía el frontend tras recibir el cargo exitoso de culqi-python.
    El frontend llama a culqi-python (POST /api/culqi/charges), obtiene el charge_id
    y luego llama a paku-backend (POST /orders/{id}/confirm-payment) para registrarlo.
    """
    culqi_charge_id: str  # chr_(test|live)_XXXXXXXXXXXXXXXX devuelto por culqi-python


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
