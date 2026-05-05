from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.pet_records.domain.record import PetRecord, RecordRole, RecordType
from app.modules.pet_records.infra.postgres_pet_records_repository import PostgresPetRecordsRepository
from app.modules.pets.domain.pet import PetRepository


@dataclass
class ListRecords:
    records_repo: PostgresPetRecordsRepository
    pets_repo: PetRepository

    async def execute(
        self,
        *,
        pet_id: UUID,
        user_id: UUID,
        role: str,
        type: Optional[RecordType] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        recorded_by_role: Optional[RecordRole] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[PetRecord]:
        pet = await self.pets_repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        if role != "admin" and pet.owner_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        return await self.records_repo.list_by_pet(
            pet_id=pet_id,
            type=type,
            date_from=date_from,
            date_to=date_to,
            role=recorded_by_role,
            limit=limit,
            offset=offset,
        )
