from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status

from app.modules.catalog.domain.breed import Breed
from app.modules.catalog.infra.postgres_breed_repository import PostgresBreedRepository


@dataclass
class ListBreeds:
    repo: PostgresBreedRepository

    async def execute(self, *, species: Optional[str] = None) -> list[Breed]:
        """Público: solo razas activas."""
        return await self.repo.list_active(species=species)


@dataclass
class ListBreedsAdmin:
    repo: PostgresBreedRepository

    async def execute(self, *, species: Optional[str] = None) -> list[Breed]:
        """Admin: todas las razas incluidas las inactivas."""
        return await self.repo.list_all(species=species)


@dataclass
class CreateBreed:
    repo: PostgresBreedRepository

    async def execute(self, *, id: str, name: str, species: str) -> Breed:
        if species not in ("dog", "cat"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="species_invalid: debe ser 'dog' o 'cat'",
            )
        try:
            return await self.repo.create(id=id, name=name, species=species)
        except ValueError as exc:
            if str(exc) == "breed_already_exists":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="breed_already_exists: ya existe una raza con ese id",
                ) from exc
            raise


@dataclass
class UpdateBreed:
    repo: PostgresBreedRepository

    async def execute(self, breed_id: str, *, name: Optional[str] = None) -> Breed:
        patch = {}
        if name is not None:
            patch["name"] = name
        try:
            return await self.repo.update(breed_id, patch)
        except ValueError as exc:
            if str(exc) == "breed_not_found":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Breed not found"
                ) from exc
            raise


@dataclass
class ToggleBreed:
    repo: PostgresBreedRepository

    async def execute(self, breed_id: str, *, is_active: bool) -> Breed:
        try:
            return await self.repo.set_active(breed_id, is_active)
        except ValueError as exc:
            if str(exc) == "breed_not_found":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Breed not found"
                ) from exc
            raise
