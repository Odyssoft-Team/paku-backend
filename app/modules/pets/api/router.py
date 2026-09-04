from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import engine, get_async_session
from app.media.gcs import to_signed_read_url_or_none
from app.modules.pets.api.schemas import PetCreateIn, PetOut, UpdatePetIn, WeightEntryIn, WeightEntryOut, PatchPetOptionalIn
from app.modules.pets.app.use_cases import CreatePet, DeletePet, GetPet, GetWeightHistory, ListPets, RecordWeight, UpdatePet, PatchPetOptional
from app.modules.pets.domain.pet import Pet, PetRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
from app.modules.catalog.infra.postgres_breed_repository import PostgresBreedRepository

router = APIRouter(tags=["pets"])
admin_router = APIRouter(tags=["pets-admin"])


def get_pet_repo(session: AsyncSession = Depends(get_async_session)) -> PetRepository:
    return PostgresPetRepository(session=session, engine=engine)


def get_breed_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresBreedRepository:
    return PostgresBreedRepository(session=session, engine=engine)


def _pet_to_out(pet: Pet) -> PetOut:
    """Construye PetOut resolviendo photo_url (object key en BD) a una signed read URL fresca."""
    data = pet.__dict__.copy()
    data["photo_url"] = to_signed_read_url_or_none(pet.photo_url)
    return PetOut(**data)


@router.post("/pets", response_model=PetOut, status_code=status.HTTP_201_CREATED)
async def create_pet(
    payload: PetCreateIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PetRepository = Depends(get_pet_repo),
    breed_repo: PostgresBreedRepository = Depends(get_breed_repo),
) -> PetOut:
    pet = await CreatePet(repo=repo, breed_repo=breed_repo).execute(
        owner_id=current.id,
        name=payload.name,
        species=payload.species,
        breed_id=payload.breed_id,
        sex=payload.sex,
        birth_date=payload.birth_date,
        notes=payload.notes,
        sterilized=payload.sterilized,
        size=payload.size,
        weight_kg=payload.weight_kg,
        activity_level=payload.activity_level,
        coat_type=payload.coat_type,
        skin_sensitivity=payload.skin_sensitivity,
        bath_behavior=payload.bath_behavior,
        tolerates_drying=payload.tolerates_drying,
        tolerates_nail_clipping=payload.tolerates_nail_clipping,
        vaccines_up_to_date=payload.vaccines_up_to_date,
        grooming_frequency=payload.grooming_frequency,
        receive_reminders=payload.receive_reminders,
        antiparasitic=payload.antiparasitic,
        antiparasitic_interval=payload.antiparasitic_interval,
        special_shampoo=payload.special_shampoo,
    )
    return _pet_to_out(pet)


@router.patch("/pets/{id}/optional", response_model=PetOut)
async def patch_pet_optional(
    id: UUID,
    payload: PatchPetOptionalIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PetRepository = Depends(get_pet_repo),
) -> PetOut:
    pet = await PatchPetOptional(repo=repo).execute(
        pet_id=id,
        owner_id=current.id,
        **{k: v for k, v in payload.dict().items() if v is not None},
    )
    return _pet_to_out(pet)


@router.get("/pets", response_model=list[PetOut])
async def list_pets(
    limit: int = Query(default=7, ge=1, le=14, description="Maximum number of pets to return"),
    offset: int = Query(default=0, ge=0, description="Number of pets to skip"),
    current: CurrentUser = Depends(get_current_user),
    repo: PetRepository = Depends(get_pet_repo),
) -> list[PetOut]:
    pets = await ListPets(repo=repo).execute(
        owner_id=current.id,
        limit=limit,
        offset=offset,
    )
    return [_pet_to_out(pet) for pet in pets]


@router.get("/pets/{id}", response_model=PetOut)
async def get_pet(id: UUID, repo: PetRepository = Depends(get_pet_repo)) -> PetOut:
    pet = await GetPet(repo=repo).execute(pet_id=id)
    return _pet_to_out(pet)


@router.put("/pets/{id}", response_model=PetOut)
async def update_pet(
    id: UUID,
    payload: UpdatePetIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PetRepository = Depends(get_pet_repo),
    breed_repo: PostgresBreedRepository = Depends(get_breed_repo),
) -> PetOut:
    pet = await UpdatePet(repo=repo, breed_repo=breed_repo).execute(
        pet_id=id,
        owner_id=current.id,
        name=payload.name,
        breed_id=payload.breed_id,
        sex=payload.sex,
        birth_date=payload.birth_date,
        notes=payload.notes,
        photo_url=None,  # managed exclusively via POST /media/confirm-profile-photo
    )
    return _pet_to_out(pet)


@router.post("/pets/{id}/weight", response_model=WeightEntryOut, status_code=status.HTTP_201_CREATED)
async def record_weight(
    id: UUID,
    payload: WeightEntryIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PetRepository = Depends(get_pet_repo),
) -> WeightEntryOut:
    entry = await RecordWeight(repo=repo).execute(
        pet_id=id,
        owner_id=current.id,
        weight_kg=payload.weight_kg,
    )
    return WeightEntryOut(**entry.__dict__)


@router.delete("/pets/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PetRepository = Depends(get_pet_repo),
) -> None:
    await DeletePet(repo=repo).execute(
        pet_id=id,
        user_id=current.id,
        role=getattr(current, "role", "owner"),
    )


@router.get("/pets/{id}/weight-history", response_model=list[WeightEntryOut])
async def get_weight_history(id: UUID, repo: PetRepository = Depends(get_pet_repo)) -> list[WeightEntryOut]:
    entries = await GetWeightHistory(repo=repo).execute(pet_id=id)
    return [WeightEntryOut(**e.__dict__) for e in entries]


# ------------------------------------------------------------------
# Admin
# ------------------------------------------------------------------

@admin_router.get("/users/{user_id}/pets", response_model=list[PetOut])
async def admin_list_user_pets(
    user_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PetRepository = Depends(get_pet_repo),
) -> list[PetOut]:
    pets = await ListPets(repo=repo).execute(owner_id=user_id, limit=100, offset=0)
    return [_pet_to_out(pet) for pet in pets]
