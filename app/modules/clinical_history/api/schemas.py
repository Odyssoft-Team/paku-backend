from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClinicalEntryOut(BaseModel):
    id: UUID
    pet_id: UUID
    type: str
    summary: str
    created_at: datetime
