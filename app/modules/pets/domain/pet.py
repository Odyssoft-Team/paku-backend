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
    ) -> "Pet":
        return Pet(
            id=uuid4(),
            owner_id=owner_id,
            name=name,
            species=species,
            breed=breed,
            sex=sex,
            birth_date=birth_date,
            notes=notes,
            created_at=datetime.now(timezone.utc),
        )


class PetRepository(Protocol):
    async def add(self, pet: Pet) -> None:
        ...

    async def get_by_id(self, pet_id: UUID) -> Optional[Pet]:
        ...
