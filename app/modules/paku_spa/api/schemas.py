from __future__ import annotations

from typing import List

from pydantic import BaseModel


class PakuSpaPlanOut(BaseModel):
    code: str
    name: str
    description: str
    price: int
    currency: str
    includes: List[str]
