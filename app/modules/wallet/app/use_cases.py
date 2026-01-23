from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.wallet.domain.card import Card
from app.modules.wallet.infra import card_repository


@dataclass
class AddCard:
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
    ) -> Card:
        existing_cards = card_repository.list_cards(user_id)
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
        )
        return card_repository.add_card(card)


@dataclass
class ListCards:
    async def execute(self, *, user_id: UUID) -> list[Card]:
        return card_repository.list_cards(user_id)


@dataclass
class RemoveCard:
    async def execute(self, *, card_id: UUID, user_id: UUID) -> None:
        success = card_repository.remove_card(card_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found",
            )


@dataclass
class SetDefaultCard:
    async def execute(self, *, card_id: UUID, user_id: UUID) -> Card:
        card = card_repository.set_default(card_id, user_id)
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found",
            )
        return card
