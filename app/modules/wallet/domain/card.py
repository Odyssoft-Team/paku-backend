from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


# [TECH]
# Immutable domain entity for payment cards with secure token storage.
#
# [NATURAL/BUSINESS]
# Representa una tarjeta de pago guardada sin datos sensibles.
@dataclass(frozen=True)
class Card:
    id: UUID
    user_id: UUID
    provider: str
    payment_method_id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool
    created_at: datetime

    # [TECH]
    # Factory method creating Card with UUID and UTC timestamp.
    #
    # [NATURAL/BUSINESS]
    # Crea una nueva tarjeta con ID único y fecha de creación.
    @staticmethod
    def new(
        *,
        user_id: UUID,
        provider: str,
        payment_method_id: str,
        brand: str,
        last4: str,
        exp_month: int,
        exp_year: int,
        is_default: bool = False,
    ) -> "Card":
        return Card(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            payment_method_id=payment_method_id,
            brand=brand,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=is_default,
            created_at=datetime.now(timezone.utc),
        )
