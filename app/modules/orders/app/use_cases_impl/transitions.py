"""
Use cases para las transiciones de estado que ejecuta el groomer
durante el flujo del servicio (modelo van: recoge, atiende en la van y devuelve).

Flujo principal:
  created → (accepted) → on_the_way → in_service → done
  cualquier estado activo → cancelled (solo admin)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.domain.order import SERVICE_STEPS, Order, OrderStatus
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository

logger = logging.getLogger(__name__)

_STATUS_LABELS: dict[OrderStatus, tuple[str, str]] = {
    OrderStatus.accepted:   ("Servicio aceptado",       "Tu groomer aceptó el servicio."),
    OrderStatus.on_the_way: ("Groomer en camino",        "Tu groomer está en camino a tu domicilio."),
    OrderStatus.in_service: ("Tu groomer llegó",         "Tu groomer llegó para recoger a tu mascota."),
    OrderStatus.done:       ("Servicio finalizado",      "¡El servicio ha concluido! Esperamos que tu mascota esté feliz."),
    OrderStatus.cancelled:  ("Servicio cancelado",       "Tu servicio ha sido cancelado."),
}


async def notify_user(
    repo: PostgresOrderRepository, *, user_id: UUID, title: str, body: str, data: dict, type: str = "order_status",
) -> None:
    """Notificación (y push) a un usuario. Best-effort: nunca bloquea la operación."""
    try:
        from app.core.db import engine
        from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
        from app.modules.notifications.app.use_cases import CreateNotification

        notifications_repo = PostgresNotificationRepository(session=repo._session, engine=engine)
        await CreateNotification(repo=notifications_repo).execute(
            user_id=user_id, type=type, title=title, body=body, data=data,
        )
    except Exception as exc:
        logger.exception("Failed to send notification: %s", exc)


async def _notify(repo: PostgresOrderRepository, order: Order) -> None:
    """Notifica al cliente el nuevo estado de su orden."""
    title, body = _STATUS_LABELS.get(order.status, ("Estado actualizado", "Tu pedido fue actualizado."))
    data = {"order_id": str(order.id), "status": order.status.value}
    if order.service_step:
        data["service_step"] = order.service_step
    await notify_user(repo, user_id=order.user_id, title=title, body=body, data=data)


def _get_order_or_404(order: Order | None, order_id: UUID) -> Order:
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _assert_can_advance(order: Order, target: OrderStatus) -> None:
    if not order.can_advance_to(target):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"transition_invalid: no se puede pasar de '{order.status.value}' a '{target.value}'",
        )


def _assert_is_groomer(order: Order, groomer_id: UUID) -> None:
    """Verifica que el groomer autenticado es el asignado a esta orden."""
    if order.groomer_id != groomer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta orden")


# ------------------------------------------------------------------
# AcceptOrder — groomer acepta el servicio (reservado para flujo futuro)
# ------------------------------------------------------------------

@dataclass
class AcceptOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, groomer_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        _assert_is_groomer(order, groomer_id)
        _assert_can_advance(order, OrderStatus.accepted)
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.accepted)
        await _notify(self.repo, updated)
        return updated


# ------------------------------------------------------------------
# DepartOrder — groomer salió hacia el domicilio del cliente
# ------------------------------------------------------------------

@dataclass
class DepartOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, groomer_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        _assert_is_groomer(order, groomer_id)
        _assert_can_advance(order, OrderStatus.on_the_way)
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.on_the_way)
        await _notify(self.repo, updated)
        return updated


# ------------------------------------------------------------------
# ArriveOrder — groomer llegó al domicilio, inicia el servicio
# ------------------------------------------------------------------

@dataclass
class ArriveOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, groomer_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        _assert_is_groomer(order, groomer_id)
        _assert_can_advance(order, OrderStatus.in_service)
        await self.repo.set_status(id=order_id, status=OrderStatus.in_service)
        # Modelo van: al llegar empieza el proceso del servicio en "reception" (recojo + foto + pesaje).
        updated = await self.repo.set_service_step(
            id=order_id, step=SERVICE_STEPS[0], at=datetime.now(timezone.utc),
        )
        await _notify(self.repo, updated)
        return updated


# ------------------------------------------------------------------
# CompleteOrder — groomer terminó el servicio
# ------------------------------------------------------------------

@dataclass
class CompleteOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, groomer_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        _assert_is_groomer(order, groomer_id)
        _assert_can_advance(order, OrderStatus.done)
        # El último paso ("return") se cierra con /complete. Órdenes que llegaron antes de que
        # existieran los pasos (service_step vacío) se pueden completar igual.
        if order.service_step is not None and order.service_step != SERVICE_STEPS[-1]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SERVICE_STEPS_PENDING",
                    "message": f"La orden está en el paso '{order.service_step}'; avanza hasta '{SERVICE_STEPS[-1]}' antes de completar.",
                    "service_step": order.service_step,
                },
            )
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.done)
        await _notify(self.repo, updated)
        return updated


# ------------------------------------------------------------------
# CancelOrder — admin cancela desde cualquier estado activo
# ------------------------------------------------------------------

async def release_order_hold(holds_repo, order: Order) -> None:
    """La orden se canceló o se saltó: su reserva de cupo se libera (el día vuelve a tener cupo)."""
    if holds_repo is None or order.hold_id is None:
        return
    try:
        await holds_repo.release(order.hold_id)
    except Exception:
        logger.exception("No se pudo liberar la reserva %s de la orden %s", order.hold_id, order.id)


@dataclass
class CancelOrder:
    repo: PostgresOrderRepository
    holds_repo: object = None  # PostgresHoldRepository

    async def execute(self, *, order_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        if not order.can_cancel():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"cancel_invalid: no se puede cancelar una orden en estado '{order.status.value}'",
            )
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.cancelled)
        await release_order_hold(self.holds_repo, updated)
        await _notify(self.repo, updated)
        return updated
