from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.pets.domain.pet import Pet, PetRepository, Sex, Size, ActivityLevel, CoatType, BathBehavior, AntiparasiticInterval
from app.modules.pets.domain.weight_entry import PetWeightEntry


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
        sterilized: Optional[bool] = None,
        size: Optional[Size] = None,
        weight_kg: Optional[float] = None,
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
    ) -> Pet:
        pet = Pet.new(
            owner_id=owner_id,
            name=name,
            species=species,
            breed=breed,
            sex=sex,
            birth_date=birth_date,
            notes=notes,
            weight_kg=weight_kg,
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


@dataclass
class PatchPetOptional:
    repo: PetRepository

    async def execute(self, *, pet_id: UUID, owner_id: UUID, **kwargs) -> Pet:
        pet = await self.repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        if pet.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        # Construir objeto actualizado tomando valores existentes y reemplazando con kwargs cuando no sean None
        updated = Pet(
            id=pet.id,
            owner_id=pet.owner_id,
            name=kwargs.get('name', pet.name),
            species=pet.species,
            breed=kwargs.get('breed', pet.breed),
            sex=kwargs.get('sex', pet.sex),
            birth_date=kwargs.get('birth_date', pet.birth_date),
            notes=kwargs.get('notes', pet.notes),
            created_at=pet.created_at,
            photo_url=kwargs.get('photo_url', pet.photo_url),
            weight_kg=kwargs.get('weight_kg', pet.weight_kg),
            updated_at=datetime.now(timezone.utc),
            sterilized=kwargs.get('sterilized', pet.sterilized),
            size=kwargs.get('size', pet.size),
            activity_level=kwargs.get('activity_level', pet.activity_level),
            coat_type=kwargs.get('coat_type', pet.coat_type),
            skin_sensitivity=kwargs.get('skin_sensitivity', pet.skin_sensitivity),
            bath_behavior=kwargs.get('bath_behavior', pet.bath_behavior),
            tolerates_drying=kwargs.get('tolerates_drying', pet.tolerates_drying),
            tolerates_nail_clipping=kwargs.get('tolerates_nail_clipping', pet.tolerates_nail_clipping),
            vaccines_up_to_date=kwargs.get('vaccines_up_to_date', pet.vaccines_up_to_date),
            grooming_frequency=kwargs.get('grooming_frequency', pet.grooming_frequency),
            receive_reminders=kwargs.get('receive_reminders', pet.receive_reminders),
            antiparasitic=kwargs.get('antiparasitic', pet.antiparasitic),
            antiparasitic_interval=kwargs.get('antiparasitic_interval', pet.antiparasitic_interval),
            special_shampoo=kwargs.get('special_shampoo', pet.special_shampoo),
        )
        await self.repo.update(updated)
        return updated


@dataclass
class UpdatePet:
    repo: PetRepository

    async def execute(
        self,
        *,
        pet_id: UUID,
        owner_id: UUID,
        name: Optional[str] = None,
        breed: Optional[str] = None,
        sex: Optional[Sex] = None,
        birth_date: Optional[date] = None,
        notes: Optional[str] = None,
        photo_url: Optional[str] = None,
    ) -> Pet:
        pet = await self.repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        if pet.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        updated = Pet(
            id=pet.id,
            owner_id=pet.owner_id,
            name=name if name is not None else pet.name,
            species=pet.species,
            breed=breed if breed is not None else pet.breed,
            sex=sex if sex is not None else pet.sex,
            birth_date=birth_date if birth_date is not None else pet.birth_date,
            notes=notes if notes is not None else pet.notes,
            created_at=pet.created_at,
            photo_url=photo_url if photo_url is not None else pet.photo_url,
            weight_kg=pet.weight_kg,
            updated_at=datetime.now(timezone.utc),
        )
        await self.repo.update(updated)
        return updated


@dataclass
class RecordWeight:
    repo: PetRepository

    async def execute(self, *, pet_id: UUID, owner_id: UUID, weight_kg: float) -> PetWeightEntry:
        pet = await self.repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        if pet.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        entry = PetWeightEntry.new(pet_id=pet_id, weight_kg=weight_kg)
        await self.repo.add_weight_entry(entry)

        updated_pet = Pet(
            id=pet.id,
            owner_id=pet.owner_id,
            name=pet.name,
            species=pet.species,
            breed=pet.breed,
            sex=pet.sex,
            birth_date=pet.birth_date,
            notes=pet.notes,
            created_at=pet.created_at,
            photo_url=pet.photo_url,
            weight_kg=weight_kg,
            updated_at=datetime.now(timezone.utc),
        )
        await self.repo.update(updated_pet)
        return entry


@dataclass
class GetWeightHistory:
    repo: PetRepository

    async def execute(self, *, pet_id: UUID) -> List[PetWeightEntry]:
        entries = await self.repo.get_weight_history(pet_id=pet_id)
        return entries


@dataclass
class ListPets:
    repo: PetRepository

    async def execute(
        self,
        *,
        owner_id: UUID,
        limit: int = 7,
        offset: int = 0,
    ) -> List[Pet]:
        pets = await self.repo.list_by_owner(
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )
        return pets
