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
from app.core.timezone import LIMA_TZ
from app.modules.pets.domain.pet import PetRepository
from app.modules.pets.domain.weight_policy import weight_editable_from
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.orders.app.use_cases_impl.weight_balance import register_measured_weight
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository


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
    users_repo: Optional[object] = None  # PostgresUserRepository: avisos a admins por diferencia de peso

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
        elif role == "groomer":
            assigned = await self.orders_repo.is_groomer_assigned_to_pet(groomer_id=user_id, pet_id=pet_id)
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

        if type == RecordType.weight_record and role not in ("admin", "groomer"):
            # El dueño no cambia el peso con un servicio solicitado: el groomer pesa a la mascota en el
            # servicio y ese peso es el que vale (feature 0003-saldo-por-peso).
            locked = await self.orders_repo.pets_with_requested_service(pet_ids=[pet_id])
            if pet_id in locked:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "PET_WEIGHT_LOCKED",
                        "message": "No puedes cambiar el peso mientras la mascota tenga un servicio solicitado.",
                    },
                )
            # Y no a cada rato: una vez cada PET_WEIGHT_CHANGE_COOLDOWN_DAYS días (feature 0006).
            available = weight_editable_from(getattr(pet, "weight_updated_at", None))
            if available is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "PET_WEIGHT_COOLDOWN",
                        "message": "Podrás volver a actualizar el peso desde el "
                        + available.astimezone(LIMA_TZ).strftime("%d/%m/%Y") + ".",
                        "available_at": available.isoformat(),
                    },
                )

        if role == "admin":
            recorded_by_role = RecordRole.admin
        elif role == "groomer":
            recorded_by_role = RecordRole.groomer
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
            now = datetime.now(timezone.utc)
            updated_pet = replace(pet, weight_kg=new_weight, updated_at=now, weight_updated_at=now)
            await self.pets_repo.update(updated_pet)

            # Peso real del servicio: queda en la orden que se atiende, con el monto extra si el precio
            # sube (solo groomer/admin; el dueño autoreportando en casa no cuenta).
            if recorded_by_role in (RecordRole.admin, RecordRole.groomer):
                price_check = await register_measured_weight(
                    orders_repo=self.orders_repo,
                    store_repo=self.store_repo,
                    users_repo=self.users_repo,
                    pet=updated_pet,
                    weight_kg=new_weight,
                    actor_id=user_id,
                    actor_role=role,
                )

        return CreateRecordResult(record=saved, price_check=price_check)
