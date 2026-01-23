from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.push.domain.push import Platform


# [TECH]
# Input DTO for device registration with platform and token.
#
# [NATURAL/BUSINESS]
# Datos para registrar un dispositivo para notificaciones.
class DeviceRegisterIn(BaseModel):
    platform: Platform
    token: str


# [TECH]
# Output DTO serializing DeviceToken for API responses.
#
# [NATURAL/BUSINESS]
# Representación de dispositivo registrado que devuelve la API.
class DeviceOut(BaseModel):
    id: UUID
    user_id: UUID
    platform: Platform
    token: str
    is_active: bool
    created_at: datetime
