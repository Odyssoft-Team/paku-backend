from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional, Protocol
from uuid import UUID, uuid4


class Species(str, Enum):
    dog = "dog"
    cat = "cat"


class Sex(str, Enum):
    male = "male"
    female = "female"


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
        )


class PetRepository(Protocol):
    async def add(self, pet: Pet) -> None:
        ...

    async def get_by_id(self, pet_id: UUID) -> Optional[Pet]:
        ...
