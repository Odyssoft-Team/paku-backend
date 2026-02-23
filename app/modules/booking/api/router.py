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

router = APIRouter(tags=["booking"])

# ========================================
# SERVICE IDs PARA TESTING (FRONTEND)
# ========================================
# Usar estos UUIDs hardcoded para probar availability y holds en desarrollo.
# Estos IDs corresponden a los servicios seed en postgres_commerce_repository.py
#
# BASE_DOG_BATH:    11111111-1111-1111-1111-111111111111  (Baño base perro)
# BASE_CAT_GROOM:   33333333-3333-3333-3333-333333333333  (Aseo base gato)
# ADDON_DOG_NAILS:  22222222-2222-2222-2222-222222222222  (Corte de uñas)
# ADDON_DOG_TEETH:  44444444-4444-4444-4444-444444444444  (Limpieza dental)
# ADDON_DOG_HAIRCUT: 55555555-5555-5555-5555-555555555555 (Corte de pelo)
#
# Ejemplo de uso en frontend:
# GET /availability?service_id=11111111-1111-1111-1111-111111111111
# ========================================


def get_hold_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresHoldRepository:
    return PostgresHoldRepository(session=session, engine=engine)


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
) -> HoldOut:
    hold = await ConfirmHold(repo=repo).execute(hold_id=id)
    return HoldOut(**hold.__dict__)


@router.post("/holds/{id}/cancel", response_model=HoldOut)
async def cancel(id: UUID, repo: PostgresHoldRepository = Depends(get_hold_repo)) -> HoldOut:
    hold = await CancelHold(repo=repo).execute(hold_id=id)
    return HoldOut(**hold.__dict__)


@router.get("/availability", response_model=list[AvailabilityOut])
async def availability(
    service_id: UUID = Query(..., description="Use test ID: 11111111-1111-1111-1111-111111111111"),
    date_from: Optional[date] = Query(None, description="Start date (default: today)"),
    days: int = Query(7, ge=1, le=30, description="Number of days to return (1-30)"),
    _: CurrentUser = Depends(get_current_user),
) -> list[AvailabilityOut]:
    """Get availability calendar for a service (MOCK implementation for testing).
    
    Returns mock availability data. Capacity is hardcoded to 20 slots per day.
    
    **Testing with frontend:**
    - Use `service_id=11111111-1111-1111-1111-111111111111` (Base Dog Bath)
    - Or `service_id=33333333-3333-3333-3333-333333333333` (Base Cat Groom)
    
    **Example:**
    ```
    GET /availability?service_id=11111111-1111-1111-1111-111111111111&date_from=2026-02-20&days=7
    ```
    """
    capacity = 20
    start = date_from or date.today()
    out: list[AvailabilityOut] = []
    for i in range(days):
        d = start + timedelta(days=i)
        used = (d.toordinal() + int(service_id.int % 7)) % 6
        available = max(0, capacity - used)
        out.append(AvailabilityOut(date=d, capacity=capacity, available=available))
    return out
