from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.pet_records.domain.record import (
    PetRecord,
    RecordRole,
    RecordType,
    validate_record_data,
)
from app.modules.pet_records.infra.postgres_pet_records_repository import PostgresPetRecordsRepository
from app.modules.pets.domain.pet import PetRepository
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.orders.app.use_cases_impl.price_recalc import compute_price_check
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository
from app.modules.store.domain.models import Species
from app.modules.store.app.use_cases_impl.quote import _breed_category


@dataclass
class CreateRecordResult:
    record: PetRecord
    price_check: Optional[dict[str, Any]] = None


@dataclass
class CreateRecord:
    records_repo: PostgresPetRecordsRepository
    pets_repo: PetRepository
    orders_repo: PostgresOrderRepository
    store_repo: PostgresStoreRepository

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
    ) -> CreateRecordResult:
        pet = await self.pets_repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        is_owner = pet.owner_id == user_id
        if role == "admin":
            pass
        elif is_owner:
            pass
        elif role == "ally":
            assigned = await self.orders_repo.is_ally_assigned_to_pet(ally_id=user_id, pet_id=pet_id)
            if not assigned:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        missing = validate_record_data(type, data)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid record data. Missing or invalid fields: {', '.join(missing)}",
            )

        if role == "admin":
            recorded_by_role = RecordRole.admin
        elif role == "ally":
            recorded_by_role = RecordRole.ally
        else:
            recorded_by_role = RecordRole.owner

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

        price_check: Optional[dict[str, Any]] = None

        if type == RecordType.weight_record:
            new_weight = float(data["weight_kg"])
            updated_pet = replace(pet, weight_kg=new_weight, updated_at=datetime.now(timezone.utc))
            await self.pets_repo.update(updated_pet)

            # Detección de candidato a recálculo de precio (ver plan): solo si quien registra
            # es admin/ally (no el dueño autoreportando en casa) y hay una orden pagada de
            # esta mascota cuyo servicio aún no termina.
            if recorded_by_role in (RecordRole.admin, RecordRole.ally):
                order = await self.orders_repo.find_recalculation_candidate(pet_id=pet_id)
                if order is not None:
                    species = Species(str(pet.species.value if hasattr(pet.species, "value") else pet.species))
                    breed_category = _breed_category(pet.breed_id, pet.breed_name)
                    price_check = await compute_price_check(
                        store_repo=self.store_repo,
                        order=order,
                        pet_id=pet_id,
                        species=species,
                        breed_category=breed_category,
                        new_weight=new_weight,
                    )

        return CreateRecordResult(record=saved, price_check=price_check)
