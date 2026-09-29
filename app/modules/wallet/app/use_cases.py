from dataclasses import dataclass
import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.culqi_client import CulqiOperationAmbiguous, CulqiOperationFailed, CulqiPythonClient
from app.modules.iam.domain.user import UserRepository
from app.modules.wallet.domain.card import Card
from app.modules.wallet.domain.payment_customer import PaymentCustomerRepository
from app.modules.wallet.infra.postgres_card_repository import (
    CardAlreadyLinkedError,
    PostgresCardRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class AddCard:
    repo: PostgresCardRepository
    customers_repo: PaymentCustomerRepository
    users_repo: UserRepository
    culqi_client: CulqiPythonClient

    async def execute(
        self,
        *,
        user_id: UUID,
        token_id: str,
    ) -> Card:
        provider = "culqi"
        payment_customer = await self.customers_repo.get_by_user_and_provider(
            user_id=user_id,
            provider=provider,
        )

        if payment_customer is None:
            user = await self.users_repo.get_by_id(user_id)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

            payment_customer, created_by_request = await self.customers_repo.create(
                user_id=user_id,
                provider=provider,
            )
            if not created_by_request:
                if payment_customer.status != "ready" or not payment_customer.customer_id:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "CUSTOMER_PROVISIONING_PENDING",
                            "message": "La creación del Customer requiere reconciliación antes de reintentar.",
                        },
                    )
            else:
                first_name = user.first_name.strip()[:50]
                last_name = user.last_name.strip()[:50]
                if len(first_name) < 2:
                    first_name = "Usuario"
                if len(last_name) < 2:
                    last_name = "Paku"
                address = user.address.address_line.strip()[:100] if user.address else ""
                if len(address) < 5:
                    address = "Lima, Peru"
                phone_number = user.phone.strip() if user.phone else ""
                if not 5 <= len(phone_number) <= 15:
                    phone_number = "000000000"
                try:
                    customer_result = await self.culqi_client.create_customer(
                        first_name=first_name,
                        last_name=last_name,
                        email=user.email,
                        country_code="PE",
                        address=address,
                        address_city="Lima",
                        phone_number=phone_number,
                    )
                except CulqiOperationAmbiguous as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "CUSTOMER_CREATION_AMBIGUOUS",
                            "message": "El resultado requiere reconciliación; no se repetirá automáticamente.",
                        },
                    ) from exc
                except CulqiOperationFailed as exc:
                    try:
                        await self.customers_repo.delete_pending(
                            payment_customer_id=payment_customer.id
                        )
                    except SQLAlchemyError as persistence_error:
                        logger.exception("Could not release failed payment-customer reservation")
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Customer reservation cleanup failed",
                        ) from persistence_error
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Payment provider operation failed",
                    ) from exc

                customer_id = customer_result.get("id")
                if not isinstance(customer_id, str) or not customer_id:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "CUSTOMER_CREATION_AMBIGUOUS",
                            "message": "El resultado requiere reconciliación; no se repetirá automáticamente.",
                        },
                    )
                try:
                    payment_customer = await self.customers_repo.set_customer_id(
                        payment_customer_id=payment_customer.id,
                        customer_id=customer_id,
                    )
                except SQLAlchemyError as exc:
                    logger.exception("Could not persist payment provider customer mapping")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "CUSTOMER_MAPPING_PENDING",
                            "message": "El Customer fue creado; la asociación requiere reconciliación.",
                        },
                    ) from exc

        if payment_customer.status != "ready" or not payment_customer.customer_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "CUSTOMER_PROVISIONING_PENDING",
                    "message": "La creación del Customer requiere reconciliación antes de reintentar.",
                },
            )

        try:
            card_result = await self.culqi_client.create_card(
                customer_id=payment_customer.customer_id,
                token_id=token_id,
            )
        except CulqiOperationAmbiguous as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "CARD_CREATION_AMBIGUOUS",
                    "message": "El resultado de la tarjeta es incierto; verifica el Wallet antes de reintentar.",
                },
            ) from exc
        except CulqiOperationFailed as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment provider operation failed",
            ) from exc

        card_id = card_result.get("id")
        source = card_result.get("source") or {}
        if not isinstance(source, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment provider returned an invalid card",
            )
        iin = source.get("iin") or {}
        if not isinstance(iin, dict):
            iin = {}
        brand = iin.get("card_brand") or source.get("card_brand")
        last4 = source.get("last_four") or source.get("last4")
        if (
            not isinstance(card_id, str)
            or not card_id
            or not isinstance(brand, str)
            or not brand
            or not isinstance(last4, str)
            or len(last4) != 4
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "CARD_CREATION_AMBIGUOUS",
                    "message": "El resultado de la tarjeta es incierto; verifica el Wallet antes de reintentar.",
                },
            )

        try:
            exp_month = int(source.get("expiration_month") or 0)
            exp_year = int(source.get("expiration_year") or 0)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "CARD_CREATION_AMBIGUOUS",
                    "message": "El resultado de la tarjeta es incierto; verifica el Wallet antes de reintentar.",
                },
            ) from exc

        existing_cards = await self.repo.list_cards(user_id)

        card = Card.new(
            user_id=user_id,
            provider=provider,
            payment_method_id=card_id,
            brand=str(brand),
            last4=str(last4),
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=len(existing_cards) == 0,
            culqi_card_id=card_id,
        )
        try:
            return await self.repo.add_card(card)
        except CardAlreadyLinkedError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment card is already linked to another user",
            ) from exc
        except SQLAlchemyError as exc:
            logger.exception("Could not persist payment card in wallet")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "CARD_PERSISTENCE_FAILED",
                    "message": "La Card fue creada por el proveedor, pero no quedó confirmada en Wallet; verifica antes de reintentar.",
                },
            ) from exc


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
