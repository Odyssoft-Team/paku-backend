from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.pets.domain.pet import Pet, PetRepository, Sex, Size, ActivityLevel, CoatType, BathBehavior, AntiparasiticInterval
from app.modules.catalog.infra.postgres_breed_repository import PostgresBreedRepository


async def _resolve_breed_name(breed_repo: PostgresBreedRepository, breed_id: Optional[str]) -> Optional[str]:
    """El front solo manda breed_id; el nombre a mostrar lo resuelve siempre el backend."""
    if not breed_id:
        return None
    breed = await breed_repo.get(breed_id)
    if breed is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="breed_id_invalid: no existe una raza con ese id",
        )
    return breed.name


@dataclass
class CreatePet:
    repo: PetRepository
    breed_repo: PostgresBreedRepository

    async def execute(
        self,
        *,
        owner_id: UUID,
        name: str,
        species: str,
        breed_id: Optional[str] = None,
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
        breed_name = await _resolve_breed_name(self.breed_repo, breed_id)
        pet = Pet.new(
            owner_id=owner_id,
            name=name,
            species=species,
            breed_id=breed_id,
            breed_name=breed_name,
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
        try:
            await self.repo.add(pet)
        except ValueError as exc:
            if str(exc) == "breed_id_invalid":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="breed_id_invalid: no existe una raza con ese id",
                ) from exc
            raise
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
class DeletePet:
    repo: PetRepository

    async def execute(self, *, pet_id: UUID, user_id: UUID, role: str) -> None:
        pet = await self.repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        if role != "admin" and pet.owner_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        deleted = await self.repo.soft_delete(pet_id, datetime.now(timezone.utc))
        if deleted is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        # NOTA: holds/cart NO se tocan (booking/cart desconectados del checkout).
        return None


@dataclass
class PatchPetOptional:
    repo: PetRepository

    async def execute(self, *, pet_id: UUID, owner_id: UUID, **kwargs) -> Pet:
        pet = await self.repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        if pet.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        # weight_kg ya no se acepta aquí — el único camino para cambiar peso es
        # POST /pets/{pet_id}/records (type=weight_record), para dejar historial.
        kwargs.pop('weight_kg', None)

        # Construir objeto actualizado tomando valores existentes y reemplazando con kwargs cuando no sean None
        updated = replace(
            pet,
            name=kwargs.get('name', pet.name),
            breed_id=kwargs.get('breed_id', pet.breed_id),
            breed_name=kwargs.get('breed_name', pet.breed_name),
            sex=kwargs.get('sex', pet.sex),
            birth_date=kwargs.get('birth_date', pet.birth_date),
            notes=kwargs.get('notes', pet.notes),
            photo_url=kwargs.get('photo_url', pet.photo_url),
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
        try:
            await self.repo.update(updated)
        except ValueError as exc:
            if str(exc) == "breed_id_invalid":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="breed_id_invalid: no existe una raza con ese id",
                ) from exc
            raise
        return updated


@dataclass
class UpdatePet:
    repo: PetRepository
    breed_repo: PostgresBreedRepository

    async def execute(
        self,
        *,
        pet_id: UUID,
        owner_id: UUID,
        name: Optional[str] = None,
        breed_id: Optional[str] = None,
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

        breed_name = await _resolve_breed_name(self.breed_repo, breed_id) if breed_id is not None else pet.breed_name
        # dataclasses.replace preserva TODO campo no mencionado aquí (incluidos los de detalle
        # de /optional) — antes se reconstruía Pet(...) a mano y se perdían silenciosamente.
        updated = replace(
            pet,
            name=name if name is not None else pet.name,
            breed_id=breed_id if breed_id is not None else pet.breed_id,
            breed_name=breed_name,
            sex=sex if sex is not None else pet.sex,
            birth_date=birth_date if birth_date is not None else pet.birth_date,
            notes=notes if notes is not None else pet.notes,
            photo_url=photo_url if photo_url is not None else pet.photo_url,
            updated_at=datetime.now(timezone.utc),
        )
        try:
            await self.repo.update(updated)
        except ValueError as exc:
            if str(exc) == "breed_id_invalid":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="breed_id_invalid: no existe una raza con ese id",
                ) from exc
            raise
        return updated


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
