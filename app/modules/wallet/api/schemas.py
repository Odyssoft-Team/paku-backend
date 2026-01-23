from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CardIn(BaseModel):
    provider: str
    payment_method_id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int


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
