from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.pets.api.schemas import PetCreateIn, PetOut, UpdatePetIn, WeightEntryIn, WeightEntryOut, PatchPetOptionalIn
from app.modules.pets.app.use_cases import CreatePet, GetPet, GetWeightHistory, ListPets, RecordWeight, UpdatePet, PatchPetOptional
from app.modules.pets.domain.pet import PetRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository

router = APIRouter(tags=["pets"])


def get_pet_repo(session: AsyncSession = Depends(get_async_session)) -> PetRepository:
    return PostgresPetRepository(session=session, engine=engine)


@router.post("/pets", response_model=PetOut, status_code=status.HTTP_201_CREATED)
async def create_pet(
    payload: PetCreateIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PetRepository = Depends(get_pet_repo),
) -> PetOut:
    pet = await CreatePet(repo=repo).execute(
        owner_id=current.id,
        name=payload.name,
        species=payload.species,
        breed=payload.breed,
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
    return PetOut(**pet.__dict__)


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
    return PetOut(**pet.__dict__)


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
    return [PetOut(**pet.__dict__) for pet in pets]


@router.get("/pets/{id}", response_model=PetOut)
async def get_pet(id: UUID, repo: PetRepository = Depends(get_pet_repo)) -> PetOut:
    pet = await GetPet(repo=repo).execute(pet_id=id)
    return PetOut(**pet.__dict__)


@router.put("/pets/{id}", response_model=PetOut)
async def update_pet(
    id: UUID,
    payload: UpdatePetIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PetRepository = Depends(get_pet_repo),
) -> PetOut:
    pet = await UpdatePet(repo=repo).execute(
        pet_id=id,
        owner_id=current.id,
        name=payload.name,
        breed=payload.breed,
        sex=payload.sex,
        birth_date=payload.birth_date,
        notes=payload.notes,
        photo_url=payload.photo_url,
    )
    return PetOut(**pet.__dict__)


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


@router.get("/pets/{id}/weight-history", response_model=list[WeightEntryOut])
async def get_weight_history(id: UUID, repo: PetRepository = Depends(get_pet_repo)) -> list[WeightEntryOut]:
    entries = await GetWeightHistory(repo=repo).execute(pet_id=id)
    return [WeightEntryOut(**e.__dict__) for e in entries]
