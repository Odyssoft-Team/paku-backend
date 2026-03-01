"""
Use cases para las transiciones de estado que ejecuta el ally/groomer
durante el flujo del servicio a domicilio.

Flujo principal:
  created → (accepted) → on_the_way → in_service → done
  cualquier estado activo → cancelled (solo admin)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.domain.order import Order, OrderStatus
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository

logger = logging.getLogger(__name__)

_STATUS_LABELS: dict[OrderStatus, tuple[str, str]] = {
    OrderStatus.accepted:   ("Servicio aceptado",       "Tu groomer aceptó el servicio."),
    OrderStatus.on_the_way: ("Groomer en camino",        "Tu groomer está en camino a tu domicilio."),
    OrderStatus.in_service: ("¡El grooming comenzó!",   "Tu mascota está siendo atendida por nuestro groomer."),
    OrderStatus.done:       ("Servicio finalizado",      "¡El servicio ha concluido! Esperamos que tu mascota esté feliz."),
    OrderStatus.cancelled:  ("Servicio cancelado",       "Tu servicio ha sido cancelado."),
}


async def _notify(repo: PostgresOrderRepository, order: Order) -> None:
    """Envía notificación push al cliente. Best-effort: no bloquea."""
    try:
        from app.core.db import engine
        from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
        from app.modules.notifications.app.use_cases import CreateNotification

        title, body = _STATUS_LABELS.get(order.status, ("Estado actualizado", "Tu pedido fue actualizado."))
        notifications_repo = PostgresNotificationRepository(session=repo._session, engine=engine)
        await CreateNotification(repo=notifications_repo).execute(
            user_id=order.user_id,
            type="order_status",
            title=title,
            body=body,
            data={"order_id": str(order.id), "status": order.status.value},
        )
    except Exception as exc:
        logger.exception("Failed to send order status notification: %s", exc)


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


def _assert_is_ally(order: Order, ally_id: UUID) -> None:
    """Verifica que el ally autenticado es el asignado a esta orden."""
    if order.ally_id != ally_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta orden")


# ------------------------------------------------------------------
# AcceptOrder — ally acepta el servicio (reservado para flujo futuro)
# ------------------------------------------------------------------

@dataclass
class AcceptOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, ally_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        _assert_is_ally(order, ally_id)
        _assert_can_advance(order, OrderStatus.accepted)
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.accepted)
        await _notify(self.repo, updated)
        return updated


# ------------------------------------------------------------------
# DepartOrder — ally salió hacia el domicilio del cliente
# ------------------------------------------------------------------

@dataclass
class DepartOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, ally_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        _assert_is_ally(order, ally_id)
        _assert_can_advance(order, OrderStatus.on_the_way)
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.on_the_way)
        await _notify(self.repo, updated)
        return updated


# ------------------------------------------------------------------
# ArriveOrder — ally llegó al domicilio, inicia el servicio
# ------------------------------------------------------------------

@dataclass
class ArriveOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, ally_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        _assert_is_ally(order, ally_id)
        _assert_can_advance(order, OrderStatus.in_service)
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.in_service)
        await _notify(self.repo, updated)
        return updated


# ------------------------------------------------------------------
# CompleteOrder — ally terminó el servicio
# ------------------------------------------------------------------

@dataclass
class CompleteOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, ally_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        _assert_is_ally(order, ally_id)
        _assert_can_advance(order, OrderStatus.done)
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.done)
        await _notify(self.repo, updated)
        return updated


# ------------------------------------------------------------------
# CancelOrder — admin cancela desde cualquier estado activo
# ------------------------------------------------------------------

@dataclass
class CancelOrder:
    repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID) -> Order:
        order = _get_order_or_404(await self.repo.get_order_admin(id=order_id), order_id)
        if not order.can_cancel():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"cancel_invalid: no se puede cancelar una orden en estado '{order.status.value}'",
            )
        updated = await self.repo.set_status(id=order_id, status=OrderStatus.cancelled)
        await _notify(self.repo, updated)
        return updated
