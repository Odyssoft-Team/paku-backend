from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status

from app.modules.catalog.domain.breed import COAT_TYPES, Breed, coat_group_for
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

    async def execute(self, *, id: str, name: str, species: str, fields: Optional[dict] = None) -> Breed:
        if species not in ("dog", "cat"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="species_invalid: debe ser 'dog' o 'cat'",
            )
        try:
            return await self.repo.create(id=id, name=name, species=species, extra=_breed_fields(fields))
        except ValueError as exc:
            if str(exc) == "breed_already_exists":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="breed_already_exists: ya existe una raza con ese id",
                ) from exc
            raise


def _breed_fields(fields: Optional[dict]) -> dict:
    """Valida y normaliza los campos editables por el admin. El grupo se deriva del pelaje."""
    out = dict(fields or {})
    if "coat_type" in out:
        coat = out["coat_type"] or None
        if coat is not None and coat not in COAT_TYPES:
            raise HTTPException(status_code=422, detail={
                "code": "COAT_TYPE_INVALID",
                "message": "Tipo de pelaje inválido. Usa uno de: " + ", ".join(COAT_TYPES) + " o null.",
            })
        out["coat_type"] = coat
        out["coat_group"] = coat_group_for(coat)
    for key in ("photo_url", "description"):
        if key in out and isinstance(out[key], str):
            out[key] = out[key].strip() or None
    photo = out.get("photo_url")
    if photo and not photo.startswith(("catalog/", "http://", "https://")):
        raise HTTPException(status_code=422, detail={
            "code": "PHOTO_URL_INVALID",
            "message": "La foto debe subirse con POST /media/signed-upload (entity_type=catalog) o ser una URL.",
        })
    return out


@dataclass
class UpdateBreed:
    repo: PostgresBreedRepository

    async def execute(self, breed_id: str, *, name: Optional[str] = None, fields: Optional[dict] = None) -> Breed:
        """`fields`: solo las claves enviadas (coat_type, is_mixed, photo_url, description)."""
        patch = _breed_fields(fields)
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
