from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.orders.domain.order import OrderStatus, PaymentMethod, PaymentStatus


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
    # Pago: pending → verifying → paid | failed (ver POST /orders/{id}/pay)
    payment_status: PaymentStatus = PaymentStatus.pending
    culqi_charge_id: Optional[str] = None  # chr_(test|live)_XXXXXXXXXXXXXXXX
    payment_method: Optional[PaymentMethod] = None  # card | yape | cash
    parent_order_id: Optional[UUID] = None  # presente solo en órdenes de ajuste


class ConfirmPaymentIn(BaseModel):
    """
    Fallback manual: registra un charge_id ya confirmado por otra vía (soporte).
    El camino principal es POST /orders/{id}/pay, que orquesta el cobro directamente.
    """
    culqi_charge_id: str  # chr_(test|live)_XXXXXXXXXXXXXXXX devuelto por culqi-python


class CreateAdjustmentIn(BaseModel):
    """Payload para POST /orders/{id}/create-adjustment — qué mascota disparó el recálculo."""
    pet_id: UUID


class PayOrderIn(BaseModel):
    """
    Payload para POST /orders/{id}/pay. Solo el token — el monto, moneda, order_id y
    demás datos del cargo los arma paku-backend con lo que ya tiene guardado en la orden,
    para que el cliente no pueda influir en cuánto se le cobra.
    """
    source_id: str  # tkn_(test|live)_..., ype_(test|live)_... o crd_(test|live)_...


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
