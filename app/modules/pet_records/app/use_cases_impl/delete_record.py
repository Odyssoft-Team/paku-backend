from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.pet_records.domain.record import PetRecord
from app.modules.pet_records.infra.postgres_pet_records_repository import PostgresPetRecordsRepository
from app.modules.pets.domain.pet import PetRepository


@dataclass
class DeleteRecord:
    records_repo: PostgresPetRecordsRepository
    pets_repo: PetRepository

    async def execute(
        self,
        *,
        pet_id: UUID,
        record_id: UUID,
        user_id: UUID,
        role: str,
    ) -> PetRecord:
        pet = await self.pets_repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        if role != "admin" and pet.owner_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        record = await self.records_repo.get_by_id(record_id)
        if not record or record.pet_id != pet_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

        if record.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

        deleted = await self.records_repo.soft_delete(record_id, datetime.now(timezone.utc))
        return deleted or record
