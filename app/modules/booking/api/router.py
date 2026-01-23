from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.booking.api.schemas import AvailabilityOut, HoldCreateIn, HoldOut
from app.modules.booking.app.use_cases import CancelHold, ConfirmHold, CreateHold

router = APIRouter(tags=["booking"])


@router.post("/holds", response_model=HoldOut, status_code=status.HTTP_201_CREATED)
async def create(payload: HoldCreateIn, current: CurrentUser = Depends(get_current_user)) -> HoldOut:
    hold = CreateHold().execute(user_id=current.id, pet_id=payload.pet_id, service_id=payload.service_id)
    return HoldOut(**hold.__dict__)


@router.post("/holds/{id}/confirm", response_model=HoldOut)
async def confirm(id: UUID) -> HoldOut:
    hold = ConfirmHold().execute(hold_id=id)
    return HoldOut(**hold.__dict__)


@router.post("/holds/{id}/cancel", response_model=HoldOut)
async def cancel(id: UUID) -> HoldOut:
    hold = CancelHold().execute(hold_id=id)
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
