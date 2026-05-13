from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.wallet.domain.card import Card


class PostgresCardRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_card(r) -> Card:
        return Card(
            id=r.id,
            user_id=r.user_id,
            provider=r.provider,
            payment_method_id=r.payment_method_id,
            brand=r.brand,
            last4=r.last4,
            exp_month=r.exp_month,
            exp_year=r.exp_year,
            is_default=r.is_default,
            created_at=r.created_at,
            culqi_customer_id=r.culqi_customer_id,
            culqi_card_id=r.culqi_card_id,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def add_card(self, card: Card) -> Card:
        from app.modules.wallet.infra.models import WalletCardModel
        model = WalletCardModel(
            id=card.id,
            user_id=card.user_id,
            provider=card.provider,
            payment_method_id=card.payment_method_id,
            brand=card.brand,
            last4=card.last4,
            exp_month=card.exp_month,
            exp_year=card.exp_year,
            is_default=card.is_default,
            culqi_customer_id=card.culqi_customer_id,
            culqi_card_id=card.culqi_card_id,
            created_at=card.created_at,
        )
        self._session.add(model)
        await self._session.commit()
        return card

    async def remove_card(self, card_id: UUID, user_id: UUID) -> bool:
        from app.modules.wallet.infra.models import WalletCardModel
        result = await self._session.execute(
            select(WalletCardModel).where(
                WalletCardModel.id == card_id,
                WalletCardModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True

    async def set_default(self, card_id: UUID, user_id: UUID) -> Optional[Card]:
        from app.modules.wallet.infra.models import WalletCardModel
        # Verificar que la tarjeta existe y pertenece al usuario
        result = await self._session.execute(
            select(WalletCardModel).where(
                WalletCardModel.id == card_id,
                WalletCardModel.user_id == user_id,
            )
        )
        target = result.scalar_one_or_none()
        if target is None:
            return None

        # Quitar default de todas las tarjetas del usuario
        await self._session.execute(
            update(WalletCardModel)
            .where(WalletCardModel.user_id == user_id)
            .values(is_default=False)
        )
        # Marcar la seleccionada como default
        await self._session.execute(
            update(WalletCardModel)
            .where(WalletCardModel.id == card_id)
            .values(is_default=True)
        )
        await self._session.commit()

        # Refrescar y devolver
        result = await self._session.execute(
            select(WalletCardModel).where(WalletCardModel.id == card_id)
        )
        row = result.scalar_one()
        return self._row_to_card(row)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_cards(self, user_id: UUID) -> List[Card]:
        from app.modules.wallet.infra.models import WalletCardModel
        result = await self._session.execute(
            select(WalletCardModel)
            .where(WalletCardModel.user_id == user_id)
            .order_by(WalletCardModel.is_default.desc(), WalletCardModel.created_at)
        )
        return [self._row_to_card(r) for r in result.scalars().all()]

    async def get_card(self, card_id: UUID) -> Optional[Card]:
        from app.modules.wallet.infra.models import WalletCardModel
        result = await self._session.execute(
            select(WalletCardModel).where(WalletCardModel.id == card_id)
        )
        row = result.scalar_one_or_none()
        return self._row_to_card(row) if row else None
