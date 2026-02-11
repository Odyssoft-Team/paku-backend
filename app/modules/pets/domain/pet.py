from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional, Protocol
from uuid import UUID, uuid4

from app.modules.pets.domain.weight_entry import PetWeightEntry


class Species(str, Enum):
    dog = "dog"
    cat = "cat"


class Sex(str, Enum):
    male = "male"
    female = "female"


class Size(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


class ActivityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CoatType(str, Enum):
    short = "short"
    medium = "medium"
    long = "long"


class BathBehavior(str, Enum):
    calm = "calm"
    fearful = "fearful"
    anxious = "anxious"


class AntiparasiticInterval(str, Enum):
    monthly = "monthly"
    trimestral = "trimestral"


@dataclass(frozen=True)
class Pet:
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

    # Nuevos campos
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

    @staticmethod
    def new(
        *,
        owner_id: UUID,
        name: str,
        species: Species,
        breed: Optional[str] = None,
        sex: Optional[Sex] = None,
        birth_date: Optional[date] = None,
        notes: Optional[str] = None,
        photo_url: Optional[str] = None,
        weight_kg: Optional[float] = None,
        sterilized: Optional[bool] = None,
        size: Optional[Size] = None,
        activity_level: Optional[ActivityLevel] = None,
        coat_type: Optional[CoatType] = None,
        skin_sensitivity: Optional[bool] = None,
        bath_behavior: Optional[BathBehavior] = None,
        tolerates_drying: Optional[bool] = None,
        tolerates_nail_clipping: Optional[bool] = None,
        vaccines_up_to_date: Optional[bool] = None,
        grooming_frequency: Optional[str] = None,
        receive_reminders: Optional[bool] = None,
        antiparasitic: Optional[bool] = None,
        antiparasitic_interval: Optional[AntiparasiticInterval] = None,
        special_shampoo: Optional[bool] = None,
    ) -> "Pet":
        now = datetime.now(timezone.utc)
        return Pet(
            id=uuid4(),
            owner_id=owner_id,
            name=name,
            species=species,
            breed=breed,
            sex=sex,
            birth_date=birth_date,
            notes=notes,
            created_at=now,
            photo_url=photo_url,
            weight_kg=weight_kg,
            updated_at=now,
            sterilized=sterilized,
            size=size,
            activity_level=activity_level,
            coat_type=coat_type,
            skin_sensitivity=skin_sensitivity,
            bath_behavior=bath_behavior,
            tolerates_drying=tolerates_drying,
            tolerates_nail_clipping=tolerates_nail_clipping,
            vaccines_up_to_date=vaccines_up_to_date,
            grooming_frequency=grooming_frequency,
            receive_reminders=receive_reminders,
            antiparasitic=antiparasitic,
            antiparasitic_interval=antiparasitic_interval,
            special_shampoo=special_shampoo,
        )


class PetRepository(Protocol):
    async def add(self, pet: Pet) -> None:
        ...

    async def get_by_id(self, pet_id: UUID) -> Optional[Pet]:
        ...

    async def update(self, pet: Pet) -> None:
        ...

    async def add_weight_entry(self, entry: PetWeightEntry) -> None:
        ...

    async def get_weight_history(self, pet_id: UUID) -> list[PetWeightEntry]:
        ...

    async def list_by_owner(self, owner_id: UUID, limit: int = 7, offset: int = 0) -> list[Pet]:
        ...
