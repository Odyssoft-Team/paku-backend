import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.auth import CurrentUser
from app.core.culqi_client import (
    CulqiOperationAmbiguous,
    CulqiOperationFailed,
    CulqiPythonClient,
)
from app.modules.wallet.app.use_cases import AddCard
from app.modules.wallet.domain.payment_customer import PaymentCustomer
from app.modules.wallet.api.schemas import CardIn, CardOut
from app.modules.wallet.domain.card import Card
from app.modules.iam.infra.models import UserModel
from app.modules.wallet.infra.models import UserPaymentCustomerModel, WalletCardModel
from app.modules.wallet.infra.postgres_card_repository import (
    CardAlreadyLinkedError,
    PostgresCardRepository,
)
from app.modules.wallet.infra.postgres_payment_customer_repository import (
    PostgresPaymentCustomerRepository,
)


class _FakeCardsRepository:
    def __init__(self, fail_add=False):
        self.cards = []
        self.fail_add = fail_add

    async def list_cards(self, user_id):
        return self.cards

    async def add_card(self, card):
        if self.fail_add:
            raise SQLAlchemyError("test persistence failure")
        self.cards.append(card)
        return card


class _FakeCustomersRepository:
    def __init__(self, customer=None):
        self.customer = customer
        self.created = []
        self._lock = asyncio.Lock()

    async def get_by_user_and_provider(self, *, user_id, provider):
        if self.customer is None:
            return None
        if self.customer.user_id != user_id or self.customer.provider != provider:
            return None
        return self.customer

    async def create(self, *, user_id, provider):
        async with self._lock:
            existing = await self.get_by_user_and_provider(user_id=user_id, provider=provider)
            if existing is not None:
                return existing, False
            self.created.append((user_id, provider))
            self.customer = PaymentCustomer.new_pending(user_id=user_id, provider=provider)
            return self.customer, True

    async def set_customer_id(self, *, payment_customer_id, customer_id):
        self.customer = replace(self.customer, customer_id=customer_id, status="ready")
        return self.customer

    async def delete_pending(self, *, payment_customer_id):
        if self.customer and self.customer.id == payment_customer_id:
            self.customer = None


class _FakeUsersRepository:
    def __init__(self, user):
        self.user = user

    async def get_by_id(self, user_id):
        return self.user if self.user.id == user_id else None


class _FakeCulqiClient:
    def __init__(self, *, customer_result=None, card_result=None, fail_at=None):
        self.customer_result = customer_result or {"id": "cus_test_1234567890123456"}
        self.card_result = card_result or {
            "id": "crd_test_1234567890123456",
            "source": {
                "iin": {"card_brand": "visa"},
                "last_four": "4242",
            },
        }
        self.fail_at = fail_at
        self.customer_calls = []
        self.card_calls = []

    async def create_customer(self, **payload):
        self.customer_calls.append(payload)
        await asyncio.sleep(0)
        if self.fail_at == "customer":
            raise CulqiOperationFailed()
        if self.fail_at == "ambiguous_customer":
            raise CulqiOperationAmbiguous()
        return self.customer_result

    async def create_card(self, **payload):
        self.card_calls.append(payload)
        await asyncio.sleep(0)
        if self.fail_at == "card":
            raise CulqiOperationFailed()
        if self.fail_at == "ambiguous_card":
            raise CulqiOperationAmbiguous()
        return self.card_result


def _user(user_id):
    return SimpleNamespace(
        id=user_id,
        email="owner@example.test",
        first_name="Paku",
        last_name="Owner",
        phone="999999999",
        address=None,
    )


def _use_case(*, customer=None, fail_at=None):
    user_id = uuid4()
    cards_repo = _FakeCardsRepository()
    customers_repo = _FakeCustomersRepository(customer)
    culqi_client = _FakeCulqiClient(fail_at=fail_at)
    use_case = AddCard(
        repo=cards_repo,
        customers_repo=customers_repo,
        users_repo=_FakeUsersRepository(_user(user_id)),
        culqi_client=culqi_client,
    )
    return user_id, use_case, cards_repo, customers_repo, culqi_client


def test_add_card_creates_customer_and_persists_provider_card():
    user_id, use_case, cards_repo, customers_repo, culqi_client = _use_case()

    card = asyncio.run(use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"))

    assert len(culqi_client.customer_calls) == 1
    assert customers_repo.created == [(user_id, "culqi")]
    assert customers_repo.customer.customer_id == "cus_test_1234567890123456"
    assert customers_repo.customer.status == "ready"
    assert culqi_client.card_calls == [
        {"customer_id": "cus_test_1234567890123456", "token_id": "tkn_test_1234567890123456"}
    ]
    assert card.user_id == user_id
    assert card.provider == "culqi"
    assert card.payment_method_id == "crd_test_1234567890123456"
    assert card.culqi_customer_id is None
    assert card.brand == "visa"
    assert card.last4 == "4242"
    assert card.is_default is True
    assert cards_repo.cards == [card]


def test_add_card_reuses_customer_for_user_and_provider():
    user_id = uuid4()
    customer = PaymentCustomer(
        id=uuid4(),
        user_id=user_id,
        provider="culqi",
        customer_id="cus_test_1234567890123456",
        status="ready",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _, use_case, _, customers_repo, culqi_client = _use_case(customer=customer)
    use_case.users_repo = _FakeUsersRepository(_user(user_id))

    asyncio.run(use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"))

    assert culqi_client.customer_calls == []
    assert customers_repo.created == []
    assert culqi_client.card_calls[0]["customer_id"] == customer.customer_id


@pytest.mark.parametrize("fail_at", ["customer", "card"])
def test_add_card_maps_provider_failure_to_502_and_does_not_persist_card(fail_at):
    user_id, use_case, cards_repo, customers_repo, _ = _use_case(fail_at=fail_at)

    with pytest.raises(HTTPException) as error:
        asyncio.run(use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"))

    assert error.value.status_code == 502
    assert cards_repo.cards == []
    if fail_at == "customer":
        assert customers_repo.customer is None


def test_card_input_only_accepts_a_culqi_token():
    payload = CardIn(token_id="tkn_test_1234567890123456")

    assert payload.token_id == "tkn_test_1234567890123456"
    assert not hasattr(payload, "user_id")
    for forbidden_field in ("user_id", "customer_id", "culqi_customer_id"):
        with pytest.raises(ValueError):
            CardIn(token_id="tkn_test_1234567890123456", **{forbidden_field: "client-value"})


def test_payment_customer_has_user_provider_uniqueness_and_user_foreign_key():
    unique_constraints = [
        constraint
        for constraint in UserPaymentCustomerModel.__table__.constraints
        if constraint.name == "uq_user_payment_customers_user_provider"
    ]
    user_foreign_keys = [
        foreign_key
        for foreign_key in UserPaymentCustomerModel.__table__.foreign_keys
        if foreign_key.parent.name == "user_id"
    ]

    assert len(unique_constraints) == 1
    assert [column.name for column in unique_constraints[0].columns] == ["user_id", "provider"]
    assert len(user_foreign_keys) == 1
    assert user_foreign_keys[0].target_fullname == "users.id"
    assert "culqi_customer_id" not in CardOut.model_fields
    assert "culqi_card_id" not in CardOut.model_fields
    check_constraints = {
        constraint.name
        for constraint in UserPaymentCustomerModel.__table__.constraints
    }
    assert "ck_user_payment_customers_status_customer_id" in check_constraints

    unique_card_index = next(
        index
        for index in WalletCardModel.__table__.indexes
        if index.name == "uq_wallet_cards_provider_culqi_card_id"
    )
    assert unique_card_index.unique is True
    assert [column.name for column in unique_card_index.columns] == ["provider", "culqi_card_id"]


def test_ambiguous_customer_result_keeps_reservation_and_retry_does_not_create_another():
    user_id, use_case, _, customers_repo, culqi_client = _use_case(fail_at="ambiguous_customer")

    with pytest.raises(HTTPException) as first_error:
        asyncio.run(use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"))
    with pytest.raises(HTTPException) as retry_error:
        asyncio.run(use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"))

    assert first_error.value.status_code == 503
    assert retry_error.value.status_code == 503
    assert customers_repo.customer.status == "provisioning"
    assert len(culqi_client.customer_calls) == 1


def test_concurrent_requests_for_same_user_create_only_one_customer():
    user_id, use_case, _, customers_repo, culqi_client = _use_case()

    async def run_concurrently():
        return await asyncio.gather(
            use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"),
            use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"),
            return_exceptions=True,
        )

    results = asyncio.run(run_concurrently())

    assert len(culqi_client.customer_calls) == 1
    assert len(customers_repo.created) == 1
    assert sum(isinstance(result, HTTPException) and result.status_code == 503 for result in results) == 1


@pytest.mark.parametrize("user_id", [uuid4(), uuid4()])
def test_wallet_route_uses_only_authenticated_user_id(monkeypatch, user_id):
    import app.core.settings

    monkeypatch.setattr(app.core.settings.settings, "DATABASE_URL", "sqlite+aiosqlite://")
    import app.modules.wallet.api.router as wallet_router

    captured = []

    class _AddCardSpy:
        def __init__(self, **_kwargs):
            pass

        async def execute(self, *, user_id, token_id):
            captured.append((user_id, token_id))
            from app.modules.wallet.domain.card import Card

            return Card.new(
                user_id=user_id,
                provider="culqi",
                payment_method_id="crd_test_1234567890123456",
                brand="visa",
                last4="4242",
                exp_month=0,
                exp_year=0,
                culqi_card_id="crd_test_1234567890123456",
            )

    monkeypatch.setattr(wallet_router, "AddCard", _AddCardSpy)
    monkeypatch.setattr(wallet_router, "PostgresPaymentCustomerRepository", lambda **_kwargs: object())
    monkeypatch.setattr(wallet_router, "PostgresUserRepository", lambda **_kwargs: object())
    monkeypatch.setattr(wallet_router, "CulqiPythonClient", lambda: object())
    current = CurrentUser(
        id=user_id,
        email="owner@example.test",
        role="user",
        is_active=True,
    )

    asyncio.run(
        wallet_router.add_card(
            CardIn(token_id="tkn_test_1234567890123456"),
            current,
            _FakeCardsRepository(),
            object(),
        )
    )

    assert captured == [(user_id, "tkn_test_1234567890123456")]


def test_wallet_card_persistence_failure_returns_explicit_partial_state():
    user_id, use_case, _, _, culqi_client = _use_case()
    use_case.repo = _FakeCardsRepository(fail_add=True)

    with pytest.raises(HTTPException) as error:
        asyncio.run(use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"))

    assert error.value.status_code == 503
    assert error.value.detail["code"] == "CARD_PERSISTENCE_FAILED"
    assert len(culqi_client.card_calls) == 1


def test_ambiguous_card_creation_is_not_reported_as_a_definite_failure():
    user_id, use_case, cards_repo, _, _ = _use_case(fail_at="ambiguous_card")

    with pytest.raises(HTTPException) as error:
        asyncio.run(use_case.execute(user_id=user_id, token_id="tkn_test_1234567890123456"))

    assert error.value.status_code == 503
    assert error.value.detail["code"] == "CARD_CREATION_AMBIGUOUS"
    assert cards_repo.cards == []


def test_payment_customer_repository_persists_unique_reservation_and_closes_read_transaction(tmp_path):
    async def run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'wallet-test.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(UserModel.__table__.create)
            await connection.run_sync(UserPaymentCustomerModel.__table__.create)

        user_id = uuid4()
        now = datetime.now(timezone.utc)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.test",
                    role="user",
                    first_name="Paku",
                    last_name="Owner",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        async with AsyncSession(engine, expire_on_commit=False) as session:
            repo = PostgresPaymentCustomerRepository(session=session)
            mapping, created = await repo.create(user_id=user_id, provider="culqi")
            assert created is True
            assert mapping.status == "provisioning"
            assert mapping.customer_id is None
            assert not session.in_transaction()

            found = await repo.get_by_user_and_provider(user_id=user_id, provider="culqi")
            assert found is not None
            assert found.id == mapping.id
            assert not session.in_transaction()

            duplicate, created_duplicate = await repo.create(user_id=user_id, provider="culqi")
            assert created_duplicate is False
            assert duplicate.id == mapping.id

        await engine.dispose()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("provider_status_code", "expected_error"),
    [
        (422, CulqiOperationFailed),
        (503, CulqiOperationAmbiguous),
    ],
)
def test_culqi_python_502_preserves_provider_ambiguity(
    monkeypatch, provider_status_code, expected_error
):
    class _Response:
        status_code = 502

        def json(self):
            return {"detail": {"provider_status_code": provider_status_code}}

    class _AsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return _Response()

    monkeypatch.setattr("app.core.culqi_client.httpx.AsyncClient", _AsyncClient)
    client = CulqiPythonClient()

    with pytest.raises(expected_error):
        asyncio.run(
            client.create_customer(
                first_name="Paku",
                last_name="Owner",
                email="owner@example.test",
                country_code="PE",
                address="Lima, Peru",
                address_city="Lima",
                phone_number="999999999",
            )
        )


def test_postgres_card_repository_is_idempotent_for_same_owner_and_rejects_other_owner(tmp_path):
    async def run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'wallet-cards.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(WalletCardModel.__table__.create)

        user_id = uuid4()

        def new_card(owner_id):
            return Card.new(
                user_id=owner_id,
                provider="culqi",
                payment_method_id="crd_test_1234567890123456",
                brand="visa",
                last4="4242",
                exp_month=0,
                exp_year=0,
                culqi_card_id="crd_test_1234567890123456",
            )

        async with AsyncSession(engine, expire_on_commit=False) as session:
            repo = PostgresCardRepository(session=session, engine=engine)
            original = await repo.add_card(new_card(user_id))
            retry = await repo.add_card(new_card(user_id))
            assert retry.id == original.id

            with pytest.raises(CardAlreadyLinkedError):
                await repo.add_card(new_card(uuid4()))

        await engine.dispose()

    asyncio.run(run())