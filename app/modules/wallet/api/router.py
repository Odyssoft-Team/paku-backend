from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.culqi_client import CulqiPythonClient
from app.core.db import engine, get_async_session
from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository
from app.modules.wallet.api.schemas import CardIn, CardOut
from app.modules.wallet.app.use_cases import AddCard, ListCards, RemoveCard, SetDefaultCard
from app.modules.wallet.infra.postgres_card_repository import PostgresCardRepository
from app.modules.wallet.infra.postgres_payment_customer_repository import PostgresPaymentCustomerRepository

router = APIRouter(tags=["wallet"], prefix="/wallet")


def get_card_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresCardRepository:
    return PostgresCardRepository(session=session, engine=engine)


@router.post("/cards", response_model=CardOut, status_code=status.HTTP_201_CREATED)
async def add_card(
    payload: CardIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCardRepository = Depends(get_card_repo),
    session: AsyncSession = Depends(get_async_session),
) -> CardOut:
    card = await AddCard(
        repo=repo,
        customers_repo=PostgresPaymentCustomerRepository(session=session),
        users_repo=PostgresUserRepository(session=session, engine=engine),
        culqi_client=CulqiPythonClient(),
    ).execute(
        user_id=current.id,
        token_id=payload.token_id,
    )
    return CardOut(**card.__dict__)


@router.get("/cards", response_model=list[CardOut])
async def list_cards(
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCardRepository = Depends(get_card_repo),
) -> list[CardOut]:
    cards = await ListCards(repo=repo).execute(user_id=current.id)
    return [CardOut(**c.__dict__) for c in cards]


@router.delete("/cards/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_card(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCardRepository = Depends(get_card_repo),
) -> None:
    await RemoveCard(repo=repo).execute(card_id=id, user_id=current.id)


@router.put("/cards/{id}/default", response_model=CardOut)
async def set_default_card(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCardRepository = Depends(get_card_repo),
) -> CardOut:
    card = await SetDefaultCard(repo=repo).execute(card_id=id, user_id=current.id)
    return CardOut(**card.__dict__)

