from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.booking.api.schemas import AvailabilityOut, HoldCreateIn, HoldOut
from app.modules.booking.app.use_cases import CancelHold, ConfirmHold, CreateHold
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
from app.modules.commerce.infra.postgres_commerce_repository import PostgresCommerceRepository
from app.modules.pets.domain.pet import PetRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository

router = APIRouter(tags=["booking"])


def get_hold_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresHoldRepository:
    return PostgresHoldRepository(session=session, engine=engine)


def get_commerce_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresCommerceRepository:
    return PostgresCommerceRepository(session=session, engine=engine)


def get_pets_repo(session: AsyncSession = Depends(get_async_session)) -> PetRepository:
    return PostgresPetRepository(session=session, engine=engine)


@router.post("/holds", response_model=HoldOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: HoldCreateIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresHoldRepository = Depends(get_hold_repo),
) -> HoldOut:
    hold = await CreateHold(repo=repo).execute(user_id=current.id, pet_id=payload.pet_id, service_id=payload.service_id)
    return HoldOut(**hold.__dict__)


@router.post("/holds/{id}/confirm", response_model=HoldOut)
async def confirm(
    id: UUID,
    repo: PostgresHoldRepository = Depends(get_hold_repo),
    commerce_repo: PostgresCommerceRepository = Depends(get_commerce_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
) -> HoldOut:
    hold = await ConfirmHold(repo=repo, commerce_repo=commerce_repo, pets_repo=pets_repo).execute(hold_id=id)
    return HoldOut(**hold.__dict__)


@router.post("/holds/{id}/cancel", response_model=HoldOut)
async def cancel(id: UUID, repo: PostgresHoldRepository = Depends(get_hold_repo)) -> HoldOut:
    hold = await CancelHold(repo=repo).execute(hold_id=id)
    return HoldOut(**hold.__dict__)


@router.get("/availability", response_model=list[AvailabilityOut])
async def availability(
    service_id: UUID = Query(...),
    date_from: Optional[date] = Query(None),
    days: int = Query(7, ge=1, le=30),
    _: CurrentUser = Depends(get_current_user),
) -> list[AvailabilityOut]:
    capacity = 20
    start = date_from or date.today()
    out: list[AvailabilityOut] = []
    for i in range(days):
        d = start + timedelta(days=i)
        used = (d.toordinal() + int(service_id.int % 7)) % 6
        available = max(0, capacity - used)
        out.append(AvailabilityOut(date=d, capacity=capacity, available=available))
    return out
