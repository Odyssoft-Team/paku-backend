from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import engine, get_async_session
from app.modules.booking.api.schemas import (
    AvailabilityOut,
    AvailabilitySlotCreateIn,
    AvailabilitySlotToggleIn,
    AvailabilitySlotUpdateIn,
    HoldCreateIn,
    HoldOut,
)
from app.modules.booking.app.use_cases import (
    CancelHold,
    ConfirmHold,
    CreateAvailabilitySlot,
    CreateHold,
    ListAvailability,
    ToggleAvailabilitySlot,
    UpdateAvailabilitySlot,
)
from app.modules.booking.infra.postgres_availability_repository import PostgresAvailabilityRepository
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository

router = APIRouter(tags=["booking"])


def get_hold_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresHoldRepository:
    return PostgresHoldRepository(session=session, engine=engine)


def get_availability_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresAvailabilityRepository:
    return PostgresAvailabilityRepository(session=session, engine=engine)


# ------------------------------------------------------------------
# Holds
# ------------------------------------------------------------------

@router.post("/holds", response_model=HoldOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: HoldCreateIn,
    current: CurrentUser = Depends(get_current_user),
    hold_repo: PostgresHoldRepository = Depends(get_hold_repo),
    availability_repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
) -> HoldOut:
    hold = await CreateHold(hold_repo=hold_repo, availability_repo=availability_repo).execute(
        user_id=current.id,
        pet_id=payload.pet_id,
        service_id=payload.service_id,
        date=payload.date,
    )
    return HoldOut(**hold.__dict__)


@router.post("/holds/{id}/confirm", response_model=HoldOut)
async def confirm(
    id: UUID,
    _: CurrentUser = Depends(get_current_user),
    repo: PostgresHoldRepository = Depends(get_hold_repo),
) -> HoldOut:
    hold = await ConfirmHold(repo=repo).execute(hold_id=id)
    return HoldOut(**hold.__dict__)


@router.post("/holds/{id}/cancel", response_model=HoldOut)
async def cancel(
    id: UUID,
    _: CurrentUser = Depends(get_current_user),
    hold_repo: PostgresHoldRepository = Depends(get_hold_repo),
    availability_repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
) -> HoldOut:
    hold = await CancelHold(hold_repo=hold_repo, availability_repo=availability_repo).execute(hold_id=id)
    return HoldOut(**hold.__dict__)


# ------------------------------------------------------------------
# Availability (public — solo slots activos con cupo)
# ------------------------------------------------------------------

@router.get("/availability", response_model=list[AvailabilityOut])
async def availability(
    service_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    days: int = Query(7, ge=1, le=30),
    _: CurrentUser = Depends(get_current_user),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
) -> list[AvailabilityOut]:
    slots = await ListAvailability(repo=repo).execute(
        service_id=service_id,
        date_from=date_from,
        days=days,
        active_only=True,
    )
    return [
        AvailabilityOut(
            id=s.id,
            service_id=s.service_id,
            date=s.date,
            capacity=s.capacity,
            booked=s.booked,
            available=s.available,
            is_active=s.is_active,
        )
        for s in slots
    ]


# ------------------------------------------------------------------
# Admin — availability slots
# ------------------------------------------------------------------

@router.get("/admin/availability", response_model=list[AvailabilityOut])
async def admin_list_availability(
    service_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    days: int = Query(30, ge=1, le=90),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
) -> list[AvailabilityOut]:
    slots = await ListAvailability(repo=repo).execute(
        service_id=service_id,
        date_from=date_from,
        days=days,
        active_only=False,
    )
    return [
        AvailabilityOut(
            id=s.id,
            service_id=s.service_id,
            date=s.date,
            capacity=s.capacity,
            booked=s.booked,
            available=s.available,
            is_active=s.is_active,
        )
        for s in slots
    ]


@router.post("/admin/availability", response_model=AvailabilityOut, status_code=201)
async def admin_create_slot(
    payload: AvailabilitySlotCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
) -> AvailabilityOut:
    slot = await CreateAvailabilitySlot(repo=repo).execute(
        service_id=payload.service_id,
        date=payload.date,
        capacity=payload.capacity,
        is_active=payload.is_active,
    )
    return AvailabilityOut(
        id=slot.id,
        service_id=slot.service_id,
        date=slot.date,
        capacity=slot.capacity,
        booked=slot.booked,
        available=slot.available,
        is_active=slot.is_active,
    )


@router.patch("/admin/availability/{slot_id}", response_model=AvailabilityOut)
async def admin_update_slot(
    slot_id: UUID,
    payload: AvailabilitySlotUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
) -> AvailabilityOut:
    slot = await UpdateAvailabilitySlot(repo=repo).execute(slot_id, capacity=payload.capacity)
    return AvailabilityOut(
        id=slot.id,
        service_id=slot.service_id,
        date=slot.date,
        capacity=slot.capacity,
        booked=slot.booked,
        available=slot.available,
        is_active=slot.is_active,
    )


@router.post("/admin/availability/{slot_id}/toggle", response_model=AvailabilityOut)
async def admin_toggle_slot(
    slot_id: UUID,
    payload: AvailabilitySlotToggleIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
) -> AvailabilityOut:
    slot = await ToggleAvailabilitySlot(repo=repo).execute(slot_id, is_active=payload.is_active)
    return AvailabilityOut(
        id=slot.id,
        service_id=slot.service_id,
        date=slot.date,
        capacity=slot.capacity,
        booked=slot.booked,
        available=slot.available,
        is_active=slot.is_active,
    )
