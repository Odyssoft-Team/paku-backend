from __future__ import annotations

from typing import List

from pydantic import BaseModel


class PakuSpaPlanOut(BaseModel):
    id: str  # UUID fijo para usar en cart (ref_id)
    code: str  # Para identificación legible (classic, premium, express)
    name: str
    description: str
    price: float  # Changed from int to float for precision
    currency: str
    includes: List[str]
