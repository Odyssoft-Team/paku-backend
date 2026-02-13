from __future__ import annotations

from typing import List

from fastapi import APIRouter

from app.modules.paku_spa.api.schemas import PakuSpaPlanOut
from app.modules.paku_spa.domain.plans_data import PLANS


router = APIRouter(prefix="/paku-spa", tags=["paku-spa"])


@router.get("/plans", response_model=List[PakuSpaPlanOut])
async def list_plans() -> List[PakuSpaPlanOut]:
    return [PakuSpaPlanOut(**p) for p in PLANS]
