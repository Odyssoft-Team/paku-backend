from typing import Dict, Optional
from uuid import UUID

from app.modules.pets.domain.pet import Pet, PetRepository


class InMemoryPetRepository(PetRepository):
    def __init__(self) -> None:
        self._by_id: Dict[UUID, Pet] = {}

    async def add(self, pet: Pet) -> None:
        self._by_id[pet.id] = pet

    async def get_by_id(self, pet_id: UUID) -> Optional[Pet]:
        return self._by_id.get(pet_id)
