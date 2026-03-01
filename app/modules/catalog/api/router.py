from __future__ import annotations

from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import engine, get_async_session
from app.modules.catalog.api.schemas import (
    BreedCreateIn,
    BreedItemOut,
    BreedOut,
    BreedsBySpeciesOut,
    BreedToggleIn,
    BreedUpdateIn,
)
from app.modules.catalog.app.use_cases import (
    CreateBreed,
    ListBreeds,
    ListBreedsAdmin,
    ToggleBreed,
    UpdateBreed,
)
from app.modules.catalog.infra.postgres_breed_repository import PostgresBreedRepository

router = APIRouter(prefix="/catalog", tags=["catalog"])
admin_router = APIRouter(tags=["catalog-admin"])


def _get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresBreedRepository:
    return PostgresBreedRepository(session=session, engine=engine)


def _group_by_species(breeds) -> list[dict]:
    """Agrupa lista de Breed por species — mantiene el contrato de respuesta original."""
    groups: dict[str, list] = defaultdict(list)
    for b in breeds:
        groups[b.species].append({"id": b.id, "name": b.name})
    # orden estable: dog primero, cat segundo
    order = ["dog", "cat"]
    result = []
    for sp in order:
        if sp in groups:
            result.append({"species": sp, "breeds": groups[sp]})
    # cualquier otra especie que se añada en el futuro
    for sp in groups:
        if sp not in order:
            result.append({"species": sp, "breeds": groups[sp]})
    return result


# ------------------------------------------------------------------
# Público — contrato idéntico al anterior
# ------------------------------------------------------------------

@router.get("/breeds", response_model=List[BreedsBySpeciesOut])
async def list_breeds(
    species: Optional[str] = Query(None, description="Filtrar por especie: dog|cat"),
    repo: PostgresBreedRepository = Depends(_get_repo),
):
    """Catálogo de razas activas, agrupado por especie."""
    breeds = await ListBreeds(repo=repo).execute(species=species)
    return _group_by_species(breeds)


# ------------------------------------------------------------------
# Admin — gestión del catálogo de razas
# ------------------------------------------------------------------

@admin_router.get("/breeds", response_model=List[BreedOut])
async def admin_list_breeds(
    species: Optional[str] = Query(None, description="Filtrar por especie: dog|cat"),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresBreedRepository = Depends(_get_repo),
):
    """Lista todas las razas (activas e inactivas)."""
    breeds = await ListBreedsAdmin(repo=repo).execute(species=species)
    return [BreedOut(id=b.id, name=b.name, species=b.species, is_active=b.is_active) for b in breeds]


@admin_router.post("/breeds", response_model=BreedOut, status_code=status.HTTP_201_CREATED)
async def admin_create_breed(
    payload: BreedCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresBreedRepository = Depends(_get_repo),
):
    """Crea una nueva raza en el catálogo."""
    breed = await CreateBreed(repo=repo).execute(
        id=payload.id.strip().lower(),
        name=payload.name,
        species=payload.species,
    )
    return BreedOut(id=breed.id, name=breed.name, species=breed.species, is_active=breed.is_active)


@admin_router.patch("/breeds/{breed_id}", response_model=BreedOut)
async def admin_update_breed(
    breed_id: str,
    payload: BreedUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresBreedRepository = Depends(_get_repo),
):
    """Actualiza el nombre de una raza."""
    breed = await UpdateBreed(repo=repo).execute(breed_id, name=payload.name)
    return BreedOut(id=breed.id, name=breed.name, species=breed.species, is_active=breed.is_active)


@admin_router.post("/breeds/{breed_id}/toggle", response_model=BreedOut)
async def admin_toggle_breed(
    breed_id: str,
    payload: BreedToggleIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresBreedRepository = Depends(_get_repo),
):
    """Activa o desactiva una raza del catálogo."""
    breed = await ToggleBreed(repo=repo).execute(breed_id, is_active=payload.is_active)
    return BreedOut(id=breed.id, name=breed.name, species=breed.species, is_active=breed.is_active)
