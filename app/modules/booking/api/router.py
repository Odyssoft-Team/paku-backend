from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_profile_complete, require_roles
from app.core.db import engine, get_async_session
from app.modules.booking.api.schemas import (
    AvailabilityOut,
    AvailabilitySlotBulkCreateIn,
    AvailabilitySlotBulkOut,
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
    CreateAvailabilitySlotsBulk,
    CreateHold,
    ListAvailability,
    ToggleAvailabilitySlot,
    UpdateAvailabilitySlot,
)
from app.modules.booking.infra.postgres_availability_repository import PostgresAvailabilityRepository
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

router = APIRouter(tags=["booking"])


def get_hold_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresHoldRepository:
    return PostgresHoldRepository(session=session, engine=engine)


def get_availability_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresAvailabilityRepository:
    return PostgresAvailabilityRepository(session=session, engine=engine)


def get_store_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresStoreRepository:
    return PostgresStoreRepository(session=session, engine=engine)


async def _to_availability_out(slots, store_repo: PostgresStoreRepository) -> list[AvailabilityOut]:
    """Resuelve service_name en batch (una sola query) para no golpear la BD por fila."""
    service_ids = {s.service_id for s in slots}
    names = await store_repo.get_product_names_by_ids(list(service_ids))
    return [
        AvailabilityOut(
            id=s.id,
            service_id=s.service_id,
            service_name=names.get(s.service_id),
            date=s.date,
            capacity=s.capacity,
            booked=s.booked,
            available=s.available,
            is_active=s.is_active,
        )
        for s in slots
    ]


# ------------------------------------------------------------------
# Holds
# ------------------------------------------------------------------

@router.post("/holds", response_model=HoldOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: HoldCreateIn,
    current: CurrentUser = Depends(require_profile_complete()),
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
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> list[AvailabilityOut]:
    slots = await ListAvailability(repo=repo).execute(
        service_id=service_id,
        date_from=date_from,
        days=days,
        active_only=True,
    )
    return await _to_availability_out(slots, store_repo)


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
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> list[AvailabilityOut]:
    slots = await ListAvailability(repo=repo).execute(
        service_id=service_id,
        date_from=date_from,
        days=days,
        active_only=False,
    )
    return await _to_availability_out(slots, store_repo)


@router.post("/admin/availability", response_model=AvailabilityOut, status_code=201)
async def admin_create_slot(
    payload: AvailabilitySlotCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> AvailabilityOut:
    slot = await CreateAvailabilitySlot(repo=repo).execute(
        service_id=payload.service_id,
        date=payload.date,
        capacity=payload.capacity,
        is_active=payload.is_active,
    )
    out = await _to_availability_out([slot], store_repo)
    return out[0]


@router.post("/admin/availability/bulk", response_model=AvailabilitySlotBulkOut, status_code=201)
async def admin_create_slots_bulk(
    payload: AvailabilitySlotBulkCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> AvailabilitySlotBulkOut:
    """
    Crea slots para un rango de fechas continuo (inclusive en ambos extremos) en una sola
    llamada. Fechas que ya tenían slot para ese service_id (UniqueConstraint(service_id, date))
    se omiten y se listan en `skipped`, no se sobreescriben.
    """
    created, skipped = await CreateAvailabilitySlotsBulk(repo=repo).execute(
        service_id=payload.service_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        capacity=payload.capacity,
        is_active=payload.is_active,
    )
    created_out = await _to_availability_out(created, store_repo)
    return AvailabilitySlotBulkOut(created=created_out, skipped=skipped)


@router.patch("/admin/availability/{slot_id}", response_model=AvailabilityOut)
async def admin_update_slot(
    slot_id: UUID,
    payload: AvailabilitySlotUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> AvailabilityOut:
    slot = await UpdateAvailabilitySlot(repo=repo).execute(slot_id, capacity=payload.capacity)
    out = await _to_availability_out([slot], store_repo)
    return out[0]


@router.post("/admin/availability/{slot_id}/toggle", response_model=AvailabilityOut)
async def admin_toggle_slot(
    slot_id: UUID,
    payload: AvailabilitySlotToggleIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresAvailabilityRepository = Depends(get_availability_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> AvailabilityOut:
    slot = await ToggleAvailabilitySlot(repo=repo).execute(slot_id, is_active=payload.is_active)
    out = await _to_availability_out([slot], store_repo)
    return out[0]
