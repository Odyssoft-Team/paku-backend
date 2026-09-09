"""
Flujo de pago back-to-back: paku-backend orquesta el cobro contra culqi-python
en vez de depender de que el frontend confirme el resultado por su cuenta.

Ver plan de rediseño de pagos para el detalle completo del flujo y la resiliencia
ante caídas (estado "verifying" + cronjob de reconciliación en app/core/scheduler.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.domain.order import Order, PaymentMethod
from app.modules.orders.infra.culqi_client import (
    CulqiChargeRejected,
    CulqiPythonClient,
    CulqiResultAmbiguous,
)
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository


def _payment_method_from_source_type(source_type: str) -> PaymentMethod:
    return PaymentMethod.yape if source_type == "yape" else PaymentMethod.card


async def _notify_payment_confirmed(orders_repo: PostgresOrderRepository, order: Order) -> None:
    """Best-effort, igual patrón que ConfirmOrderPayment — nunca bloquea la respuesta."""
    try:
        from app.core.db import engine
        from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
        from app.modules.notifications.app.use_cases import CreateNotification

        notifications_repo = PostgresNotificationRepository(session=orders_repo._session, engine=engine)
        await CreateNotification(repo=notifications_repo).execute(
            user_id=order.user_id,
            type="order_status",
            title="Pago confirmado",
            body="Tu pago fue procesado correctamente. Pronto asignaremos un groomer.",
            data={"order_id": str(order.id), "payment_status": order.payment_status.value},
        )
    except Exception as exc:
        import logging
        logging.exception("Failed to create payment confirmation notification: %s", exc)


def _source_type_from_source_id(source_id: str) -> str:
    """Réplica local de la clasificación que hace culqi-python (routes.py:_detect_source_type)."""
    if source_id.startswith("ype_"):
        return "yape"
    return "card"


@dataclass
class PayOrder:
    orders_repo: PostgresOrderRepository
    culqi_client: CulqiPythonClient

    async def execute(self, *, order_id: UUID, user_id: UUID, email: str, source_id: str) -> Order:
        try:
            order = await self.orders_repo.get_order(id=order_id, user_id=user_id)
        except ValueError as exc:
            if str(exc) == "order_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from exc
            raise

        # Idempotente: si ya no está pending (paid/failed/verifying), no se reintenta el
        # cobro — se devuelve el estado actual tal cual.
        if order.payment_status.value != "pending":
            return order

        amount_centavos = int(round(order.total_snapshot * 100))
        source_type = _source_type_from_source_id(source_id)
        payment_method = _payment_method_from_source_type(source_type)

        try:
            response = await self.culqi_client.create_charge(
                order_id=str(order.id),
                amount=amount_centavos,
                currency_code=order.currency,
                email=email,
                source_id=source_id,
                metadata={"user_id": str(user_id)},
            )
        except CulqiChargeRejected:
            return await self.orders_repo.fail_payment(id=order_id, user_id=user_id)
        except CulqiResultAmbiguous:
            return await self._reconcile_or_mark_verifying(order_id=order_id, user_id=user_id)

        culqi_charge_id = response.get("id", "")
        paid_order = await self.orders_repo.confirm_payment(
            id=order_id,
            user_id=user_id,
            culqi_charge_id=culqi_charge_id,
            payment_method=payment_method,
        )
        await _notify_payment_confirmed(self.orders_repo, paid_order)
        return paid_order

    async def _reconcile_or_mark_verifying(self, *, order_id: UUID, user_id: UUID) -> Order:
        """
        No se pudo confirmar el resultado del cobro dentro de la misma request.
        Se intenta reconciliar una vez de inmediato (puede que culqi-python ya haya
        terminado de procesar aunque la respuesta original se haya perdido); si tampoco
        eso da una respuesta definitiva, la orden queda en "verifying" para que el
        cronjob de reconciliación siga intentando en segundo plano.
        """
        payments = await self.culqi_client.find_payments(order_id=str(order_id))
        if payments:
            latest = payments[0]  # ya viene ordenado por created_at desc
            if latest["status"] == "success":
                payment_method = _payment_method_from_source_type(latest["source_type"])
                paid_order = await self.orders_repo.confirm_payment(
                    id=order_id,
                    user_id=user_id,
                    culqi_charge_id=latest["culqi_charge_id"] or "",
                    payment_method=payment_method,
                )
                await _notify_payment_confirmed(self.orders_repo, paid_order)
                return paid_order
            if latest["status"] == "failed":
                return await self.orders_repo.fail_payment(id=order_id, user_id=user_id)

        return await self.orders_repo.set_verifying(id=order_id, user_id=user_id)


@dataclass
class ConfirmCashPayment:
    """
    Confirma un pago en efectivo, ejecutado por el ally asignado al momento de la
    entrega. No pasa por Culqi — descentraliza el cobro hacia la operación física.
    """
    orders_repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, ally_id: UUID) -> Order:
        try:
            order = await self.orders_repo.confirm_cash_payment(id=order_id, ally_id=ally_id)
            await _notify_payment_confirmed(self.orders_repo, order)
            return order
        except ValueError as exc:
            if str(exc) == "order_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from exc
            if str(exc) == "not_assigned_ally":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta orden") from exc
            if str(exc) == "payment_already_processed":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El pago de esta orden ya fue procesado",
                ) from exc
            raise
