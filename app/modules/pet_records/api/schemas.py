from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.pet_records.domain.record import RecordRole, RecordType


class AttachmentOut(BaseModel):
    """Preparado para futura integración con módulo media."""
    id: UUID
    url: str
    mime_type: str


class PetRecordCreateIn(BaseModel):
    type: RecordType
    occurred_at: datetime
    data: dict
    title: Optional[str] = None
    attachment_ids: list[UUID] = Field(default_factory=list)


class PetRecordOut(BaseModel):
    id: UUID
    pet_id: UUID
    type: RecordType
    title: str
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime
    recorded_by_user_id: Optional[UUID]
    recorded_by_role: RecordRole
    recorded_by_name: Optional[str] = None  # resuelto por el backend, no viene de la BD de records
    data: dict
    attachment_ids: list[UUID]
    deleted_at: Optional[datetime] = None


class PriceCheckOut(BaseModel):
    """
    Presente solo si se detectó una diferencia de precio al registrar un weight_record
    (admin/ally, con una orden pagada de esta mascota en curso). El front debe mostrar
    esto y ofrecer confirmar la generación del cobro de la diferencia
    (POST /orders/{order_id}/create-adjustment).
    """
    order_id: UUID
    old_price: float
    new_price: float
    difference: float


class PetRecordCreateOut(BaseModel):
    record: PetRecordOut
    price_check: Optional[PriceCheckOut] = None
