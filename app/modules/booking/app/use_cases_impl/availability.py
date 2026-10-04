from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.timezone import today_lima
from app.modules.booking.domain.hold import AvailabilitySlot, Hold, HoldStatus
from app.modules.booking.infra.postgres_availability_repository import PostgresAvailabilityRepository
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
from app.modules.cart.domain.cart import CART_TTL_HOURS

_MAX_BULK_RANGE_DAYS = 90


def _error(status_code: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})


async def _assert_service_exists(store_repo, service_id: UUID) -> None:
    """El cupo es por servicio (store product); sin esto la FK fallaba con 500."""
    if store_repo is None:
        return
    if await store_repo.get_product(service_id) is None:
        raise _error(status.HTTP_404_NOT_FOUND, "SERVICE_NOT_FOUND", "El servicio no existe.")


@dataclass
class CreateAvailabilitySlot:
    repo: PostgresAvailabilityRepository
    store_repo: Optional[object] = None

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
        await _assert_service_exists(self.store_repo, service_id)
        try:
            return await self.repo.create_slot(
                service_id=service_id,
                date=date,
                capacity=capacity,
                is_active=is_active,
            )
        except ValueError as exc:
            if str(exc) == "slot_exists":
                raise _error(status.HTTP_409_CONFLICT, "SLOT_EXISTS", "Ya hay cupos para ese servicio y día.") from exc
            raise


@dataclass
class CreateAvailabilitySlotsBulk:
    repo: PostgresAvailabilityRepository
    store_repo: Optional[object] = None

    async def execute(
        self,
        *,
        service_id: UUID,
        date_from: date_type,
        date_to: Optional[date_type],
        capacity: int,
        is_active: bool = True,
    ) -> tuple[List[AvailabilitySlot], List[date_type]]:
        if capacity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="capacity_invalid: debe ser mayor que 0",
            )
        end = date_to or date_from
        if end < date_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="date_range_invalid: date_to no puede ser anterior a date_from",
            )
        if (end - date_from).days + 1 > _MAX_BULK_RANGE_DAYS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"date_range_too_large: el rango no puede superar {_MAX_BULK_RANGE_DAYS} días",
            )
        await _assert_service_exists(self.store_repo, service_id)

        created: List[AvailabilitySlot] = []
        skipped: List[date_type] = []
        current = date_from
        while current <= end:
            existing = await self.repo.get_slot_for_date(service_id, current)
            if existing is not None:
                skipped.append(current)
            else:
                try:
                    slot = await self.repo.create_slot(
                        service_id=service_id,
                        date=current,
                        capacity=capacity,
                        is_active=is_active,
                    )
                    created.append(slot)
                except ValueError as exc:
                    if str(exc) != "slot_exists":
                        raise
                    skipped.append(current)  # lo creó otro request entre la lectura y el insert
            current += timedelta(days=1)

        return created, skipped


@dataclass
class UpdateAvailabilitySlot:
    repo: PostgresAvailabilityRepository

    async def execute(self, slot_id: UUID, *, capacity: int) -> AvailabilitySlot:
        if capacity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="capacity_invalid: debe ser mayor que 0",
            )
        slot = await self.repo.get_slot(slot_id)
        if slot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        if capacity < slot.booked:
            raise _error(
                status.HTTP_409_CONFLICT,
                "CAPACITY_BELOW_BOOKED",
                f"Ya hay {slot.booked} cupos reservados; la capacidad no puede ser menor.",
                booked=slot.booked,
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
        # "Hoy" en hora de Lima: el servidor corre en UTC y desde las 7 pm ya sería el día siguiente.
        start = date_from or today_lima()
        return await self.repo.list_slots(
            service_id=service_id,
            date_from=start,
            days=days,
            active_only=active_only,
        )


@dataclass
class CreateHold:
    """
    El cliente reserva un cupo del día antes de comprar. La reserva dura lo mismo que un carrito
    (CART_TTL_HOURS); al agregarla al carrito vence junto con él, y al crear la orden se confirma.
    """
    hold_repo: PostgresHoldRepository
    availability_repo: PostgresAvailabilityRepository
    pets_repo: Optional[object] = None

    async def execute(
        self, *, user_id: UUID, pet_id: UUID, service_id: UUID, date: date_type
    ) -> Hold:
        if date < today_lima():
            raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "DATE_IN_PAST", "No se puede reservar una fecha pasada.")

        if self.pets_repo is not None:
            pet = await self.pets_repo.get_by_id(pet_id)
            if pet is None:
                raise _error(status.HTTP_404_NOT_FOUND, "PET_NOT_FOUND", "Mascota no encontrada.")
            if pet.owner_id != user_id:
                raise _error(status.HTTP_403_FORBIDDEN, "PET_NOT_OWNED", "La mascota no pertenece al usuario.")

        # Una reserva vigente por mascota y día: evita que un cliente acapare cupos.
        existing = await self.hold_repo.find_active_for_pet(pet_id=pet_id, date=date)
        if existing is not None:
            raise _error(
                status.HTTP_409_CONFLICT,
                "HOLD_ALREADY_EXISTS",
                "Esta mascota ya tiene una reserva para ese día.",
                hold_id=str(existing.id),
            )

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

        expires_at = datetime.now(timezone.utc) + timedelta(hours=CART_TTL_HOURS)
        hold = await self.hold_repo.create_hold(
            user_id=user_id,
            pet_id=pet_id,
            service_id=service_id,
            expires_at=expires_at,
            date=date,
        )
        return hold


def assert_hold_access(hold: Hold, *, requester_id: UUID, requester_role: str) -> None:
    """Solo el dueño de la reserva o un admin la confirman o cancelan."""
    if requester_role != "admin" and hold.user_id != requester_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


@dataclass
class CancelHold:
    hold_repo: PostgresHoldRepository
    availability_repo: PostgresAvailabilityRepository

    async def execute(self, *, hold_id: UUID, requester_id: UUID, requester_role: str) -> Hold:
        hold = await self.hold_repo.get_hold(hold_id)
        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hold not found")
        assert_hold_access(hold, requester_id=requester_id, requester_role=requester_role)
        if hold.status == HoldStatus.cancelled:
            return hold
        if hold.status != HoldStatus.held:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Hold cannot be cancelled"
            )

        # El repositorio libera el cupo del día en la misma transacción.
        updated = await self.hold_repo.update_status(hold_id, HoldStatus.cancelled)
        return updated or hold


@dataclass
class ListMyHolds:
    hold_repo: PostgresHoldRepository

    async def execute(self, *, user_id: UUID) -> List[Hold]:
        return await self.hold_repo.list_by_user(user_id)


@dataclass
class ListSlotHolds:
    """Admin: quién reservó un día (todas las reservas del cupo, incluidas canceladas/vencidas)."""
    hold_repo: PostgresHoldRepository
    availability_repo: PostgresAvailabilityRepository

    async def execute(self, *, slot_id: UUID) -> List[Hold]:
        slot = await self.availability_repo.get_slot(slot_id)
        if slot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        return await self.hold_repo.list_by_slot(service_id=slot.service_id, date=slot.date)
