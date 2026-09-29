from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wallet.domain.payment_customer import PaymentCustomer, PaymentCustomerRepository
from app.modules.wallet.infra.models import UserPaymentCustomerModel, utcnow


def _to_domain(model: UserPaymentCustomerModel) -> PaymentCustomer:
    return PaymentCustomer(
        id=model.id,
        user_id=model.user_id,
        provider=model.provider,
        customer_id=model.customer_id,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class PostgresPaymentCustomerRepository(PaymentCustomerRepository):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_and_provider(
        self, *, user_id: UUID, provider: str
    ) -> PaymentCustomer | None:
        async with self._session.begin():
            stmt = select(UserPaymentCustomerModel).where(
                UserPaymentCustomerModel.user_id == user_id,
                UserPaymentCustomerModel.provider == provider,
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            payment_customer = _to_domain(model) if model is not None else None
        return payment_customer

    async def create(
        self, *, user_id: UUID, provider: str
    ) -> tuple[PaymentCustomer, bool]:
        payment_customer = PaymentCustomer.new_pending(
            user_id=user_id,
            provider=provider,
        )
        model = UserPaymentCustomerModel(
            id=payment_customer.id,
            user_id=payment_customer.user_id,
            provider=payment_customer.provider,
            customer_id=payment_customer.customer_id,
            status=payment_customer.status,
            created_at=payment_customer.created_at,
            updated_at=payment_customer.updated_at,
        )
        self._session.add(model)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_by_user_and_provider(user_id=user_id, provider=provider)
            if existing is not None:
                return existing, False
            raise
        return payment_customer, True

    async def set_customer_id(
        self, *, payment_customer_id: UUID, customer_id: str
    ) -> PaymentCustomer:
        model = await self._session.get(UserPaymentCustomerModel, payment_customer_id)
        if model is None:
            raise ValueError("payment_customer_not_found")
        model.customer_id = customer_id
        model.status = "ready"
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def delete_pending(self, *, payment_customer_id: UUID) -> None:
        model = await self._session.get(UserPaymentCustomerModel, payment_customer_id)
        if model is None or model.status != "provisioning":
            return
        await self._session.delete(model)
        await self._session.commit()