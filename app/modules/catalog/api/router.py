from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query

from app.modules.catalog.api.schemas import BreedsBySpeciesOut
from app.modules.catalog.domain.breeds_data import BREEDS_CATALOG


router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/breeds", response_model=List[BreedsBySpeciesOut])
async def list_breeds(species: Optional[str] = Query(None, description="Filter by species: dog|cat")):
    """Read-only breeds catalog.

    Returns a list grouped by species. If `species` is provided, returns only that group.
    """

    if species is None:
        return BREEDS_CATALOG

    s = species.strip().lower()
    return [g for g in BREEDS_CATALOG if g["species"] == s]
