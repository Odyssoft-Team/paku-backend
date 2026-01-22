from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.pets.api.schemas import PetCreateIn, PetOut
from app.modules.pets.app.use_cases import CreatePet, GetPet
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
