from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.booking.api.schemas import HoldCreateIn, HoldOut
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
