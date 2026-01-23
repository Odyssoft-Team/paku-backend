from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.pets.domain.pet import Sex, Species


class PetCreateIn(BaseModel):
    name: str
    species: Species
    breed: Optional[str] = None
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    notes: Optional[str] = None


class PetOut(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    species: Species
    breed: Optional[str]
    sex: Optional[Sex]
    birth_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    photo_url: Optional[str] = None
    weight_kg: Optional[float] = None
    updated_at: Optional[datetime] = None


class UpdatePetIn(BaseModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    notes: Optional[str] = None
    photo_url: Optional[str] = None


class WeightEntryIn(BaseModel):
    weight_kg: float


class WeightEntryOut(BaseModel):
    id: UUID
    pet_id: UUID
    weight_kg: float
    recorded_at: datetime
