from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.pets.domain.pet import Pet, PetRepository


@dataclass
class CreatePet:
    repo: PetRepository

    async def execute(
        self,
        *,
        owner_id: UUID,
        name: str,
        species: str,
        breed: Optional[str] = None,
        sex: Optional[str] = None,
        birth_date: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> Pet:
        pet = Pet.new(
            owner_id=owner_id,
            name=name,
            species=species,
            breed=breed,
            sex=sex,
            birth_date=birth_date,
            notes=notes,
        )
        await self.repo.add(pet)
        return pet


@dataclass
class GetPet:
    repo: PetRepository

    async def execute(self, pet_id: UUID) -> Pet:
        pet = await self.repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        return pet
