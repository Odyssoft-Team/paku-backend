from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class PaymentCustomer:
    id: UUID
    user_id: UUID
    provider: str
    customer_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def new_pending(*, user_id: UUID, provider: str) -> "PaymentCustomer":
        now = datetime.now(timezone.utc)
        return PaymentCustomer(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            customer_id=None,
            status="provisioning",
            created_at=now,
            updated_at=now,
        )


class PaymentCustomerRepository(Protocol):
    async def get_by_user_and_provider(
        self, *, user_id: UUID, provider: str
    ) -> PaymentCustomer | None:
        ...

    async def create(
        self, *, user_id: UUID, provider: str
    ) -> tuple[PaymentCustomer, bool]:
        """Crea la reserva única y retorna (mapping, creada_por_esta_solicitud)."""
        ...

    async def set_customer_id(
        self, *, payment_customer_id: UUID, customer_id: str
    ) -> PaymentCustomer:
        ...

    async def delete_pending(self, *, payment_customer_id: UUID) -> None:
        ...