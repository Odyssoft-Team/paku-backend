from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.wallet.domain.card import Card
from app.modules.wallet.infra.postgres_card_repository import PostgresCardRepository


@dataclass
class AddCard:
    repo: PostgresCardRepository

    async def execute(
        self,
        *,
        user_id: UUID,
        provider: str,
        payment_method_id: str,
        brand: str,
        last4: str,
        exp_month: int,
        exp_year: int,
        culqi_customer_id: Optional[str] = None,
        culqi_card_id: Optional[str] = None,
    ) -> Card:
        existing_cards = await self.repo.list_cards(user_id)
        is_default = len(existing_cards) == 0

        card = Card.new(
            user_id=user_id,
            provider=provider,
            payment_method_id=payment_method_id,
            brand=brand,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=is_default,
            culqi_customer_id=culqi_customer_id,
            culqi_card_id=culqi_card_id,
        )
        return await self.repo.add_card(card)


@dataclass
class ListCards:
    repo: PostgresCardRepository

    async def execute(self, *, user_id: UUID) -> list[Card]:
        return await self.repo.list_cards(user_id)


@dataclass
class RemoveCard:
    repo: PostgresCardRepository

    async def execute(self, *, card_id: UUID, user_id: UUID) -> None:
        success = await self.repo.remove_card(card_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found",
            )


@dataclass
class SetDefaultCard:
    repo: PostgresCardRepository

    async def execute(self, *, card_id: UUID, user_id: UUID) -> Card:
        card = await self.repo.set_default(card_id, user_id)
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found",
            )
        return card
        return card
