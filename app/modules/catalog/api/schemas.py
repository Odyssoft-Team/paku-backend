from __future__ import annotations

from typing import List

from pydantic import BaseModel


class BreedItemOut(BaseModel):
    id: str
    name: str


class BreedsBySpeciesOut(BaseModel):
    species: str
    breeds: List[BreedItemOut]
