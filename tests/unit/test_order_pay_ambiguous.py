import asyncio
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest

from app.core.culqi_client import CulqiChargeRejected, CulqiPythonClient, CulqiResultAmbiguous
from app.modules.orders.app.use_cases_impl import payment as payment_module
from app.modules.orders.app.use_cases_impl.payment import PayOrder
from app.modules.orders.domain.order import Order, PaymentMethod, PaymentStatus


class _Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _HTTPClient:
    response = None
    exception = None
    calls = []

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, path, *, json, headers):
        self.calls.append((path, json, headers))
        if self.exception is not None:
            raise self.exception
        return self.response


@pytest.mark.parametrize(
    ("outcome", "expected_exception"),
    [
        ("rejected", CulqiChargeRejected),
        ("ambiguous", CulqiResultAmbiguous),
        (None, CulqiResultAmbiguous),
    ],
)
def test_charge_http_502_is_classified_by_outcome(monkeypatch, outcome, expected_exception):
    detail = {"provider_status_code": 402}
    if outcome is not None:
        detail["outcome"] = outcome
    _HTTPClient.response = _Response(502, {"detail": detail})
    _HTTPClient.exception = None
    _HTTPClient.calls = []
    monkeypatch.setattr("app.core.culqi_client.httpx.AsyncClient", _HTTPClient)

    client = CulqiPythonClient()
    with pytest.raises(expected_exception):
        asyncio.run(
            client.create_charge(
                order_id="order-123",
                amount=2500,
                currency_code="PEN",
                email="owner@example.test",
                source_id="tkn_test_1234567890123456",
            )
        )

    path, _payload, headers = _HTTPClient.calls[0]
    assert path == "/api/culqi/charges"
    assert headers["Idempotency-Key"].startswith("order-order-123-payment-")


def test_idempotency_key_same_source_same_key_other_source_new_key(monkeypatch):
    """Reintento con el mismo token = mismo intento; otra tarjeta tras un rechazo = intento nuevo."""
    _HTTPClient.response = _Response(200, {"id": "chr_test_1234567890123456"})
    _HTTPClient.exception = None
    _HTTPClient.calls = []
    monkeypatch.setattr("app.core.culqi_client.httpx.AsyncClient", _HTTPClient)

    def _charge(source_id):
        asyncio.run(CulqiPythonClient().create_charge(
            order_id="order-123", amount=2500, currency_code="PEN", email="owner@example.test", source_id=source_id,
        ))
        return _HTTPClient.calls[-1][2]["Idempotency-Key"]

    first = _charge("tkn_test_1234567890123456")
    again = _charge("tkn_test_1234567890123456")
    other = _charge("tkn_test_abcdefghijklmnop")

    assert first == again
    assert first != other


@pytest.mark.parametrize("status_code", [503, 504])
def test_charge_service_5xx_is_ambiguous(monkeypatch, status_code):
    _HTTPClient.response = _Response(
        status_code,
        {"detail": {"outcome": "ambiguous"}},
    )
    _HTTPClient.exception = None
    _HTTPClient.calls = []
    monkeypatch.setattr("app.core.culqi_client.httpx.AsyncClient", _HTTPClient)

    with pytest.raises(CulqiResultAmbiguous):
        asyncio.run(
            CulqiPythonClient().create_charge(
                order_id="order-123",
                amount=2500,
                currency_code="PEN",
                email="owner@example.test",
                source_id="tkn_test_1234567890123456",
            )
        )


@pytest.mark.parametrize("error", [httpx.TimeoutException("timeout"), httpx.ConnectError("network")])
def test_charge_timeout_and_network_error_are_ambiguous(monkeypatch, error):
    _HTTPClient.response = None
    _HTTPClient.exception = error
    _HTTPClient.calls = []
    monkeypatch.setattr("app.core.culqi_client.httpx.AsyncClient", _HTTPClient)

    with pytest.raises(CulqiResultAmbiguous):
        asyncio.run(
            CulqiPythonClient().create_charge(
                order_id="order-123",
                amount=2500,
                currency_code="PEN",
                email="owner@example.test",
                source_id="tkn_test_1234567890123456",
            )
        )


class _FakeOrdersRepository:
    def __init__(self, order):
        self.order = order
        self.calls = []

    async def get_order(self, *, id, user_id):
        assert id == self.order.id
        assert user_id == self.order.user_id
        return self.order

    async def fail_payment(self, *, id, user_id):
        self.calls.append("fail")
        self.order = replace(self.order, payment_status=PaymentStatus.failed)
        return self.order

    async def confirm_payment(self, *, id, user_id, culqi_charge_id, payment_method=None):
        self.calls.append(("paid", culqi_charge_id, payment_method))
        self.order = replace(
            self.order,
            payment_status=PaymentStatus.paid,
            culqi_charge_id=culqi_charge_id,
            payment_method=payment_method,
        )
        return self.order

    async def set_verifying(self, *, id, user_id):
        self.calls.append("verifying")
        self.order = replace(self.order, payment_status=PaymentStatus.verifying)
        return self.order


class _FakeUsersRepository:
    async def get_by_id(self, _user_id):
        return None


class _FakeCulqiClient:
    def __init__(self, *, create_error=None, create_result=None, payments=None):
        self.create_error = create_error
        self.create_result = create_result or {"id": "chr_test_1234567890123456"}
        self.payments = payments
        self.create_calls = 0
        self.find_calls = 0

    async def create_charge(self, **_kwargs):
        self.create_calls += 1
        if self.create_error:
            raise self.create_error
        return self.create_result

    async def find_payments(self, *, order_id):
        self.find_calls += 1
        return self.payments


def _pay_order(*, create_error=None, create_result=None, payments=None):
    user_id = uuid4()
    order = Order.new(
        user_id=user_id,
        items_snapshot=[],
        total_snapshot=25,
        currency="PEN",
    )
    orders_repo = _FakeOrdersRepository(order)
    culqi_client = _FakeCulqiClient(
        create_error=create_error,
        create_result=create_result,
        payments=payments,
    )
    use_case = PayOrder(
        orders_repo=orders_repo,
        culqi_client=culqi_client,
        users_repo=_FakeUsersRepository(),
        districts_repo=object(),
    )
    return user_id, orders_repo, culqi_client, use_case


def _silence_notifications(monkeypatch):
    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(payment_module, "_notify_payment_confirmed", _noop)


def _execute(use_case, user_id):
    return asyncio.run(
        use_case.execute(
            order_id=use_case.orders_repo.order.id,
            user_id=user_id,
            email="owner@example.test",
            source_id="tkn_test_1234567890123456",
        )
    )


def test_rejected_outcome_marks_order_failed(monkeypatch):
    _silence_notifications(monkeypatch)
    user_id, orders_repo, culqi_client, use_case = _pay_order(
        create_error=CulqiChargeRejected({"outcome": "rejected"}),
    )

    order = _execute(use_case, user_id)

    assert order.payment_status == PaymentStatus.failed
    assert orders_repo.calls == ["fail"]
    assert culqi_client.find_calls == 0


def test_ambiguous_outcome_reconciles_without_marking_failed(monkeypatch):
    user_id, orders_repo, culqi_client, use_case = _pay_order(
        create_error=CulqiResultAmbiguous(),
        payments=[],
    )

    order = _execute(use_case, user_id)

    assert order.payment_status == PaymentStatus.verifying
    assert orders_repo.calls == ["verifying"]
    assert culqi_client.find_calls == 1


def test_reconciliation_success_marks_order_paid(monkeypatch):
    _silence_notifications(monkeypatch)
    user_id, orders_repo, _, use_case = _pay_order(
        create_error=CulqiResultAmbiguous(),
        payments=[
            {
                "status": "success",
                "culqi_charge_id": "chr_test_1234567890123456",
                "source_type": "card",
            }
        ],
    )

    order = _execute(use_case, user_id)

    assert order.payment_status == PaymentStatus.paid
    assert order.culqi_charge_id == "chr_test_1234567890123456"
    assert orders_repo.calls == [("paid", "chr_test_1234567890123456", PaymentMethod.card)]


def test_reconciliation_explicit_rejection_marks_order_failed():
    user_id, orders_repo, _, use_case = _pay_order(
        create_error=CulqiResultAmbiguous(),
        payments=[{"status": "failed", "outcome": "rejected"}],
    )

    order = _execute(use_case, user_id)

    assert order.payment_status == PaymentStatus.failed
    assert orders_repo.calls == ["fail"]


def test_legacy_failed_payment_without_outcome_remains_verifying():
    user_id, orders_repo, _, use_case = _pay_order(
        create_error=CulqiResultAmbiguous(),
        payments=[{"status": "failed"}],
    )

    order = _execute(use_case, user_id)

    assert order.payment_status == PaymentStatus.verifying
    assert orders_repo.calls == ["verifying"]


@pytest.mark.parametrize("payments", [None, []])
def test_missing_reconciliation_result_remains_verifying(payments):
    user_id, orders_repo, _, use_case = _pay_order(
        create_error=CulqiResultAmbiguous(),
        payments=payments,
    )

    order = _execute(use_case, user_id)

    assert order.payment_status == PaymentStatus.verifying
    assert orders_repo.calls == ["verifying"]


def test_any_success_wins_over_other_attempts():
    payments = [
        {"status": "failed", "outcome": "rejected"},
        {
            "status": "success",
            "culqi_charge_id": "chr_test_1234567890123456",
            "source_type": "card",
        },
    ]

    resolution, payment = payment_module._resolve_payment_records(payments)

    assert resolution == "paid"
    assert payment["status"] == "success"


def test_mixed_rejected_and_ambiguous_attempts_remain_verifying():
    resolution, payment = payment_module._resolve_payment_records(
        [
            {"status": "failed", "outcome": "rejected"},
            {"status": "failed"},
        ]
    )

    assert resolution == "verifying"
    assert payment is None


def test_retry_while_verifying_does_not_create_another_charge():
    user_id, _, culqi_client, use_case = _pay_order(
        create_error=CulqiResultAmbiguous(),
        payments=[],
    )

    first_order = _execute(use_case, user_id)
    second_order = _execute(use_case, user_id)

    assert first_order.payment_status == PaymentStatus.verifying
    assert second_order.payment_status == PaymentStatus.verifying
    assert culqi_client.create_calls == 1
    assert culqi_client.find_calls == 1


def test_successful_charge_path_still_marks_order_paid(monkeypatch):
    _silence_notifications(monkeypatch)
    user_id, orders_repo, culqi_client, use_case = _pay_order()

    order = _execute(use_case, user_id)

    assert order.payment_status == PaymentStatus.paid
    assert order.culqi_charge_id == "chr_test_1234567890123456"
    assert orders_repo.calls == [("paid", "chr_test_1234567890123456", PaymentMethod.card)]
    assert culqi_client.create_calls == 1