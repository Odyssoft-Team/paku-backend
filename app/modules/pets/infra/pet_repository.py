from dataclasses import replace
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from app.modules.pets.domain.pet import Pet, PetRepository
from app.modules.pets.domain.weight_entry import PetWeightEntry


class InMemoryPetRepository(PetRepository):
    def __init__(self) -> None:
        self._by_id: Dict[UUID, Pet] = {}
        self._weight_entries: Dict[UUID, List[PetWeightEntry]] = {}

    async def add(self, pet: Pet) -> None:
        self._by_id[pet.id] = pet

    async def get_by_id(self, pet_id: UUID, *, include_deleted: bool = False) -> Optional[Pet]:
        pet = self._by_id.get(pet_id)
        if pet is None:
            return None
        if pet.deleted_at is not None and not include_deleted:
            return None
        return pet

    async def update(self, pet: Pet) -> None:
        if pet.id not in self._by_id:
            raise ValueError("pet_not_found")
        self._by_id[pet.id] = pet

    async def soft_delete(self, pet_id: UUID, when: datetime) -> Optional[Pet]:
        pet = self._by_id.get(pet_id)
        if pet is None or pet.deleted_at is not None:
            return None
        updated = replace(pet, deleted_at=when, updated_at=when)
        self._by_id[pet_id] = updated
        return updated

    async def add_weight_entry(self, entry: PetWeightEntry) -> None:
        if entry.pet_id not in self._weight_entries:
            self._weight_entries[entry.pet_id] = []
        self._weight_entries[entry.pet_id].append(entry)

    async def get_weight_history(self, pet_id: UUID) -> List[PetWeightEntry]:
        entries = self._weight_entries.get(pet_id, [])
        return sorted(entries, key=lambda e: e.recorded_at, reverse=True)
