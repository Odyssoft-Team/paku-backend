from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.pet_records.domain.record import (
    PetRecord,
    RecordRole,
    RecordType,
    validate_record_data,
)
from app.modules.pet_records.infra.postgres_pet_records_repository import PostgresPetRecordsRepository
from app.modules.pets.domain.pet import Pet, PetRepository


@dataclass
class CreateRecord:
    records_repo: PostgresPetRecordsRepository
    pets_repo: PetRepository

    async def execute(
        self,
        *,
        pet_id: UUID,
        user_id: UUID,
        role: str,
        type: RecordType,
        occurred_at: datetime,
        data: dict,
        title: Optional[str] = None,
        attachment_ids: Optional[List[UUID]] = None,
    ) -> PetRecord:
        pet = await self.pets_repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        if role != "admin" and pet.owner_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        missing = validate_record_data(type, data)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid record data. Missing or invalid fields: {', '.join(missing)}",
            )

        recorded_by_role = RecordRole.admin if role == "admin" else RecordRole.owner

        try:
            record = PetRecord.new(
                pet_id=pet_id,
                type=type,
                occurred_at=occurred_at,
                data=data,
                recorded_by_role=recorded_by_role,
                recorded_by_user_id=user_id,
                title=title,
                attachment_ids=attachment_ids,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        saved = await self.records_repo.create(record)

        if type == RecordType.weight_record:
            new_weight = float(data["weight_kg"])
            updated_pet = Pet(
                id=pet.id,
                owner_id=pet.owner_id,
                name=pet.name,
                species=pet.species,
                breed=pet.breed,
                sex=pet.sex,
                birth_date=pet.birth_date,
                notes=pet.notes,
                created_at=pet.created_at,
                photo_url=pet.photo_url,
                weight_kg=new_weight,
                updated_at=datetime.now(timezone.utc),
                sterilized=pet.sterilized,
                size=pet.size,
                activity_level=pet.activity_level,
                coat_type=pet.coat_type,
                skin_sensitivity=pet.skin_sensitivity,
                bath_behavior=pet.bath_behavior,
                tolerates_drying=pet.tolerates_drying,
                tolerates_nail_clipping=pet.tolerates_nail_clipping,
                vaccines_up_to_date=pet.vaccines_up_to_date,
                grooming_frequency=pet.grooming_frequency,
                receive_reminders=pet.receive_reminders,
                antiparasitic=pet.antiparasitic,
                antiparasitic_interval=pet.antiparasitic_interval,
                special_shampoo=pet.special_shampoo,
            )
            await self.pets_repo.update(updated_pet)

        return saved
