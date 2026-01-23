from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.wallet.api.schemas import CardIn, CardOut
from app.modules.wallet.app.use_cases import AddCard, ListCards, RemoveCard, SetDefaultCard

router = APIRouter(tags=["wallet"], prefix="/wallet")


@router.post("/cards", response_model=CardOut, status_code=status.HTTP_201_CREATED)
async def add_card(payload: CardIn, current: CurrentUser = Depends(get_current_user)) -> CardOut:
    card = await AddCard().execute(
        user_id=current.id,
        provider=payload.provider,
        payment_method_id=payload.payment_method_id,
        brand=payload.brand,
        last4=payload.last4,
        exp_month=payload.exp_month,
        exp_year=payload.exp_year,
    )
    return CardOut(**card.__dict__)


@router.get("/cards", response_model=list[CardOut])
async def list_cards(current: CurrentUser = Depends(get_current_user)) -> list[CardOut]:
    cards = await ListCards().execute(user_id=current.id)
    return [CardOut(**c.__dict__) for c in cards]


@router.delete("/cards/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_card(id: UUID, current: CurrentUser = Depends(get_current_user)) -> None:
    await RemoveCard().execute(card_id=id, user_id=current.id)


@router.put("/cards/{id}/default", response_model=CardOut)
async def set_default_card(id: UUID, current: CurrentUser = Depends(get_current_user)) -> CardOut:
    card = await SetDefaultCard().execute(card_id=id, user_id=current.id)
    return CardOut(**card.__dict__)
