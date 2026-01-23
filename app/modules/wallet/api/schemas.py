from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# [TECH]
# Input DTO for card creation with provider token and metadata.
#
# [NATURAL/BUSINESS]
# Datos para agregar una tarjeta al wallet del usuario.
class CardIn(BaseModel):
    provider: str
    payment_method_id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int


# [TECH]
# Output DTO serializing Card entity for API responses.
#
# [NATURAL/BUSINESS]
# Representación de tarjeta guardada que devuelve la API.
class CardOut(BaseModel):
    id: UUID
    user_id: UUID
    provider: str
    payment_method_id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool
    created_at: datetime
