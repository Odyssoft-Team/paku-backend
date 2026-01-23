from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.push.domain.push import Platform


class DeviceRegisterIn(BaseModel):
    platform: Platform
    token: str


class DeviceOut(BaseModel):
    id: UUID
    user_id: UUID
    platform: Platform
    token: str
    is_active: bool
    created_at: datetime
