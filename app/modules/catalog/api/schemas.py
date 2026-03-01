from __future__ import annotations

from typing import List

from pydantic import BaseModel


# ------------------------------------------------------------------
# Público — misma estructura que antes (sin cambios de contrato)
# ------------------------------------------------------------------

class BreedItemOut(BaseModel):
    id: str
    name: str


class BreedsBySpeciesOut(BaseModel):
    species: str
    breeds: List[BreedItemOut]


# ------------------------------------------------------------------
# Admin
# ------------------------------------------------------------------

class BreedOut(BaseModel):
    id: str
    name: str
    species: str
    is_active: bool


class BreedCreateIn(BaseModel):
    id: str          # slug, ej: "nueva_raza" — debe ser único
    name: str
    species: str     # "dog" | "cat"


class BreedUpdateIn(BaseModel):
    name: str


class BreedToggleIn(BaseModel):
    is_active: bool
