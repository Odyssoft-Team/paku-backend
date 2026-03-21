from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


# ------------------------------------------------------------------
# Público — misma estructura que antes (sin cambios de contrato)
# ------------------------------------------------------------------

class BreedItemOut(BaseModel):
    id: str
    name: str
    coat_group: Optional[str] = None
    coat_type: Optional[str] = None


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
    coat_group: Optional[str] = None
    coat_type: Optional[str] = None


class BreedCreateIn(BaseModel):
    id: str          # slug, ej: "nueva_raza" — debe ser único
    name: str
    species: str     # "dog" | "cat"


class BreedUpdateIn(BaseModel):
    name: str


class BreedToggleIn(BaseModel):
    is_active: bool
