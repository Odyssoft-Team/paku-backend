from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.modules.orders.domain.order import OrderStatus, PaymentMethod, PaymentStatus, SkipReason
from app.modules.orders.domain.photo import OrderPhotoKind


class CreateOrderIn(BaseModel):
    cart_id: UUID
    address_id: Optional[UUID] = None


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
    # Campos de asignación (null hasta que el admin asigne)
    groomer_id: Optional[UUID] = None
    scheduled_at: Optional[datetime] = None
    hold_id: Optional[UUID] = None
    # Pago: pending → verifying → paid | failed (ver POST /orders/{id}/pay)
    payment_status: PaymentStatus = PaymentStatus.pending
    culqi_charge_id: Optional[str] = None  # chr_(test|live)_XXXXXXXXXXXXXXXX
    payment_method: Optional[PaymentMethod] = None  # card | yape | cash
    parent_order_id: Optional[UUID] = None  # presente solo en órdenes de ajuste
    # Proceso del servicio (solo con status=in_service): reception → bath → drying → finishing → return
    service_step: Optional[str] = None
    service_steps_log: list[dict[str, Any]] = []   # [{step, started_at}]
    addons_done: list[dict[str, Any]] = []         # [{addon_id, done_at}]
    # Parada saltada (status=skipped); se conserva como historial si el admin la reprograma
    skip_reason: Optional[SkipReason] = None
    skip_note: Optional[str] = None
    skipped_at: Optional[datetime] = None

    @field_validator("service_steps_log", "addons_done", mode="before")
    @classmethod
    def _none_as_empty(cls, value):
        return value or []


class GroomerPetOut(BaseModel):
    id: UUID
    name: str
    species: str
    breed_name: Optional[str] = None
    sex: Optional[str] = None
    birth_date: Optional[date] = None
    weight_kg: Optional[float] = None
    photo_url: Optional[str] = None  # signed read URL
    notes: Optional[str] = None
    skin_sensitivity: Optional[bool] = None
    bath_behavior: Optional[str] = None
    tolerates_drying: Optional[bool] = None
    tolerates_nail_clipping: Optional[bool] = None
    special_shampoo: Optional[bool] = None


class GroomerClientOut(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class GroomerAddonOut(BaseModel):
    id: str
    name: Optional[str] = None


class GroomerServiceOut(BaseModel):
    name: Optional[str] = None
    addons: list[GroomerAddonOut] = []


class GroomerOrderOut(OrderOut):
    """Parada de la ruta del groomer: la orden + mascota, cliente y servicio."""
    pet: Optional[GroomerPetOut] = None
    client: Optional[GroomerClientOut] = None
    service: Optional[GroomerServiceOut] = None


class NextStepIn(BaseModel):
    """Paso en el que el groomer cree estar: evita que un doble tap o reintento avance dos veces."""
    from_step: str


class SkipIn(BaseModel):
    reason: SkipReason
    note: Optional[str] = Field(None, max_length=500)


class DelayReportIn(BaseModel):
    delay_minutes: int = Field(..., ge=1, le=180)
    note: Optional[str] = Field(None, max_length=500)


class DelayReportOut(BaseModel):
    id: UUID
    order_id: UUID
    groomer_id: UUID
    delay_minutes: int
    note: Optional[str] = None
    created_at: datetime


class OrderPhotoIn(BaseModel):
    object_name: str  # devuelto por POST /media/signed-upload con entity_type="order"
    kind: OrderPhotoKind
    note: Optional[str] = Field(None, max_length=500)


class OrderPhotoOut(BaseModel):
    id: UUID
    kind: OrderPhotoKind
    read_url: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


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
    groomer_id: UUID
    scheduled_at: datetime   # ISO-8601, ej: "2026-03-07T16:00:00Z"
    notes: Optional[str] = None


class AssignmentOut(BaseModel):
    id: UUID
    order_id: UUID
    groomer_id: UUID
    scheduled_at: datetime
    assigned_by: UUID
    notes: Optional[str] = None
    created_at: datetime
    # Orden actualizada con los nuevos datos
    order: OrderOut
