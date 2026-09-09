from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.modules.pets.domain.pet import Sex, Species, Size, ActivityLevel, CoatType, BathBehavior, AntiparasiticInterval


class PetCreateIn(BaseModel):
    name: str
    species: Species
    breed_id: Optional[str] = None  # id/slug de `breeds`; el backend deriva breed_name a partir de este
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    notes: Optional[str] = None

    # Nuevos campos solicitados
    sterilized: Optional[bool] = None
    size: Optional[Size] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[ActivityLevel] = None
    coat_type: Optional[CoatType] = None
    skin_sensitivity: Optional[bool] = None
    bath_behavior: Optional[BathBehavior] = None
    tolerates_drying: Optional[bool] = None
    tolerates_nail_clipping: Optional[bool] = None
    vaccines_up_to_date: Optional[bool] = None
    grooming_frequency: Optional[str] = None
    receive_reminders: Optional[bool] = None
    antiparasitic: Optional[bool] = None
    antiparasitic_interval: Optional[AntiparasiticInterval] = None
    special_shampoo: Optional[bool] = None


class PetOut(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    species: Species
    breed_id: Optional[str]
    breed_name: Optional[str]
    sex: Optional[Sex]
    birth_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    photo_url: Optional[str] = None
    weight_kg: Optional[float] = None
    updated_at: Optional[datetime] = None

    # Nuevos campos en la salida
    sterilized: Optional[bool] = None
    size: Optional[Size] = None
    activity_level: Optional[ActivityLevel] = None
    coat_type: Optional[CoatType] = None
    skin_sensitivity: Optional[bool] = None
    bath_behavior: Optional[BathBehavior] = None
    tolerates_drying: Optional[bool] = None
    tolerates_nail_clipping: Optional[bool] = None
    vaccines_up_to_date: Optional[bool] = None
    grooming_frequency: Optional[str] = None
    receive_reminders: Optional[bool] = None
    antiparasitic: Optional[bool] = None
    antiparasitic_interval: Optional[AntiparasiticInterval] = None
    special_shampoo: Optional[bool] = None


class UpdatePetIn(BaseModel):
    name: Optional[str] = None
    breed_id: Optional[str] = None  # id/slug de `breeds`; el backend deriva breed_name a partir de este
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    notes: Optional[str] = None
    # photo_url se gestiona exclusivamente a través del módulo media (POST /media/confirm-profile-photo)


# Nuevo esquema para actualizar campos opcionales posteriores al registro
class PatchPetOptionalIn(BaseModel):
    # weight_kg NO va aquí — el único camino para cambiar peso es
    # POST /pets/{pet_id}/records (type=weight_record), para dejar historial.
    sterilized: Optional[bool] = None
    size: Optional[Size] = None
    activity_level: Optional[ActivityLevel] = None
    coat_type: Optional[CoatType] = None
    skin_sensitivity: Optional[bool] = None
    bath_behavior: Optional[BathBehavior] = None
    tolerates_drying: Optional[bool] = None
    tolerates_nail_clipping: Optional[bool] = None
    vaccines_up_to_date: Optional[bool] = None
    grooming_frequency: Optional[str] = None
    receive_reminders: Optional[bool] = None
    antiparasitic: Optional[bool] = None
    antiparasitic_interval: Optional[AntiparasiticInterval] = None
    special_shampoo: Optional[bool] = None
