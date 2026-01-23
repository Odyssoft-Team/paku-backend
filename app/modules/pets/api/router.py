from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.pets.api.schemas import PetCreateIn, PetOut, UpdatePetIn, WeightEntryIn, WeightEntryOut
from app.modules.pets.app.use_cases import CreatePet, GetPet, GetWeightHistory, RecordWeight, UpdatePet
from app.modules.pets.infra.pet_repository import InMemoryPetRepository

router = APIRouter(tags=["pets"])
_repo = InMemoryPetRepository()


@router.post("/pets", response_model=PetOut, status_code=status.HTTP_201_CREATED)
async def create_pet(
    payload: PetCreateIn,
    current: CurrentUser = Depends(get_current_user),
) -> PetOut:
    pet = await CreatePet(repo=_repo).execute(
        owner_id=current.id,
        name=payload.name,
        species=payload.species,
        breed=payload.breed,
        sex=payload.sex,
        birth_date=payload.birth_date,
        notes=payload.notes,
    )
    return PetOut(**pet.__dict__)


@router.get("/pets/{id}", response_model=PetOut)
async def get_pet(id: UUID) -> PetOut:
    pet = await GetPet(repo=_repo).execute(pet_id=id)
    return PetOut(**pet.__dict__)


@router.put("/pets/{id}", response_model=PetOut)
async def update_pet(
    id: UUID,
    payload: UpdatePetIn,
    current: CurrentUser = Depends(get_current_user),
) -> PetOut:
    pet = await UpdatePet(repo=_repo).execute(
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
) -> WeightEntryOut:
    entry = await RecordWeight(repo=_repo).execute(
        pet_id=id,
        owner_id=current.id,
        weight_kg=payload.weight_kg,
    )
    return WeightEntryOut(**entry.__dict__)


@router.get("/pets/{id}/weight-history", response_model=list[WeightEntryOut])
async def get_weight_history(id: UUID) -> list[WeightEntryOut]:
    entries = await GetWeightHistory(repo=_repo).execute(pet_id=id)
    return [WeightEntryOut(**e.__dict__) for e in entries]
