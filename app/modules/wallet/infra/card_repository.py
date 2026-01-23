from typing import Dict, List, Optional
from uuid import UUID

from app.modules.wallet.domain.card import Card


class InMemoryCardRepository:
    def __init__(self) -> None:
        self._by_id: Dict[UUID, Card] = {}

    def add_card(self, card: Card) -> Card:
        self._by_id[card.id] = card
        return card

    def list_cards(self, user_id: UUID) -> List[Card]:
        return [c for c in self._by_id.values() if c.user_id == user_id]

    def get_card(self, card_id: UUID) -> Optional[Card]:
        return self._by_id.get(card_id)

    def remove_card(self, card_id: UUID, user_id: UUID) -> bool:
        card = self._by_id.get(card_id)
        if not card or card.user_id != user_id:
            return False
        del self._by_id[card_id]
        return True

    def set_default(self, card_id: UUID, user_id: UUID) -> Optional[Card]:
        target = self._by_id.get(card_id)
        if not target or target.user_id != user_id:
            return None

        for card in self._by_id.values():
            if card.user_id == user_id:
                self._by_id[card.id] = Card(
                    id=card.id,
                    user_id=card.user_id,
                    provider=card.provider,
                    payment_method_id=card.payment_method_id,
                    brand=card.brand,
                    last4=card.last4,
                    exp_month=card.exp_month,
                    exp_year=card.exp_year,
                    is_default=(card.id == card_id),
                    created_at=card.created_at,
                )

        return self._by_id.get(card_id)


_repo = InMemoryCardRepository()


def add_card(card: Card) -> Card:
    return _repo.add_card(card)


def list_cards(user_id: UUID) -> List[Card]:
    return _repo.list_cards(user_id)


def get_card(card_id: UUID) -> Optional[Card]:
    return _repo.get_card(card_id)


def remove_card(card_id: UUID, user_id: UUID) -> bool:
    return _repo.remove_card(card_id, user_id)


def set_default(card_id: UUID, user_id: UUID) -> Optional[Card]:
    return _repo.set_default(card_id, user_id)
