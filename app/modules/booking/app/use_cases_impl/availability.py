from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.booking.domain.hold import AvailabilitySlot, Hold, HoldStatus
from app.modules.booking.infra.postgres_availability_repository import PostgresAvailabilityRepository
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository


@dataclass
class CreateAvailabilitySlot:
    repo: PostgresAvailabilityRepository

    async def execute(
        self,
        *,
        service_id: UUID,
        date: date_type,
        capacity: int,
        is_active: bool = True,
    ) -> AvailabilitySlot:
        if capacity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="capacity_invalid: debe ser mayor que 0",
            )
        return await self.repo.create_slot(
            service_id=service_id,
            date=date,
            capacity=capacity,
            is_active=is_active,
        )


@dataclass
class UpdateAvailabilitySlot:
    repo: PostgresAvailabilityRepository

    async def execute(self, slot_id: UUID, *, capacity: int) -> AvailabilitySlot:
        if capacity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="capacity_invalid: debe ser mayor que 0",
            )
        try:
            return await self.repo.update_slot(slot_id, {"capacity": capacity})
        except ValueError as exc:
            if str(exc) == "slot_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found") from exc
            raise


@dataclass
class ToggleAvailabilitySlot:
    repo: PostgresAvailabilityRepository

    async def execute(self, slot_id: UUID, *, is_active: bool) -> AvailabilitySlot:
        try:
            return await self.repo.toggle_slot(slot_id, is_active)
        except ValueError as exc:
            if str(exc) == "slot_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found") from exc
            raise


@dataclass
class ListAvailability:
    repo: PostgresAvailabilityRepository

    async def execute(
        self,
        *,
        service_id: Optional[UUID] = None,
        date_from: Optional[date_type] = None,
        days: int = 7,
        active_only: bool = True,
    ) -> List[AvailabilitySlot]:
        start = date_from or date_type.today()
        return await self.repo.list_slots(
            service_id=service_id,
            date_from=start,
            days=days,
            active_only=active_only,
        )


@dataclass
class CreateHold:
    hold_repo: PostgresHoldRepository
    availability_repo: PostgresAvailabilityRepository

    async def execute(
        self, *, user_id: UUID, pet_id: UUID, service_id: UUID, date: date_type
    ) -> Hold:
        slot = await self.availability_repo.get_slot_for_update(service_id, date)

        if slot is None or not slot.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="no_availability: no hay slot disponible para esa fecha y servicio",
            )
        if not slot.has_capacity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="no_capacity: el slot está lleno",
            )

        await self.availability_repo.increment_booked(slot.id)

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        hold = await self.hold_repo.create_hold(
            user_id=user_id,
            pet_id=pet_id,
            service_id=service_id,
            expires_at=expires_at,
            date=date,
        )
        return hold


@dataclass
class CancelHold:
    hold_repo: PostgresHoldRepository
    availability_repo: PostgresAvailabilityRepository

    async def execute(self, *, hold_id: UUID) -> Hold:
        hold = await self.hold_repo.get_hold(hold_id)
        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hold not found")
        if hold.status == HoldStatus.cancelled:
            return hold
        if hold.status != HoldStatus.held:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Hold cannot be cancelled"
            )

        updated = await self.hold_repo.update_status(hold_id, HoldStatus.cancelled)

        if hold.date and hold.service_id:
            slot = await self.availability_repo.get_slot_for_date(hold.service_id, hold.date)
            if slot:
                await self.availability_repo.decrement_booked(slot.id)

        return updated or hold
