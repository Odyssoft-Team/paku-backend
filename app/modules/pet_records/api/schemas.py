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
    data: dict
    attachment_ids: list[UUID]
    deleted_at: Optional[datetime] = None
