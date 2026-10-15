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
    is_mixed: bool = False                 # mestizo: el cliente elige por foto (feature 0006)
    photo_url: Optional[str] = None
    description: Optional[str] = None


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
    is_mixed: bool = False
    photo_url: Optional[str] = None
    description: Optional[str] = None


class BreedCreateIn(BaseModel):
    id: str          # slug, ej: "nueva_raza" — debe ser único
    name: str
    species: str     # "dog" | "cat"
    coat_type: Optional[str] = None   # pelaje (define el precio); null = se cobra como mestizo
    is_mixed: bool = False
    photo_url: Optional[str] = None
    description: Optional[str] = None


class BreedUpdateIn(BaseModel):
    # Solo se cambian los campos enviados; coat_type/photo_url/description en null los quitan.
    name: Optional[str] = None
    coat_type: Optional[str] = None
    is_mixed: Optional[bool] = None
    photo_url: Optional[str] = None
    description: Optional[str] = None


class BreedToggleIn(BaseModel):
    is_active: bool
