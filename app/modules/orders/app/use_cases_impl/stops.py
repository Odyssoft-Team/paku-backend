"""
Parada saltada (pedido 4) y avisos de demora (pedido 5) de la app Groomer.
Ambos notifican al cliente y a todos los usuarios con rol admin.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.app.use_cases_impl.service_flow import _conflict, _load_for_groomer
from app.modules.orders.app.use_cases_impl.transitions import notify_user, release_order_hold
from app.modules.orders.domain.delay_report import DelayReport
from app.modules.orders.domain.order import Order, OrderStatus, SkipReason

_SKIP_REASON_TEXT = {
    SkipReason.pet_not_present: "la mascota no estaba",
    SkipReason.tutor_not_present: "no se encontró al tutor",
    SkipReason.other: "otro motivo",
}

# Estados en los que el groomer puede avisar demora (antes de llegar). Incluye `created`: las órdenes
# pasan de created a on_the_way sin `accepted`, y el groomer avisa a la siguiente parada mientras
# termina la actual (pedido del front, 2026-10-05).
_DELAY_STATUSES = frozenset({OrderStatus.created, OrderStatus.accepted, OrderStatus.on_the_way})


async def _notify_admins(orders_repo, users_repo, *, title: str, body: str, data: dict) -> None:
    try:
        admins = await users_repo.list_by_role(role="admin")
    except Exception:
        import logging
        logging.exception("No se pudo obtener la lista de admins para notificar")
        return
    for admin in admins:
        await notify_user(orders_repo, user_id=admin.id, title=title, body=body, data=data)


@dataclass
class SkipStop:
    orders_repo: object
    users_repo: object
    holds_repo: object = None  # PostgresHoldRepository: la reserva del día se libera

    async def execute(
        self, *, order_id: UUID, reason: SkipReason, note: Optional[str], actor_id: UUID, actor_role: str,
    ) -> Order:
        order = await _load_for_groomer(self.orders_repo, order_id=order_id, actor_id=actor_id, actor_role=actor_role)
        if not order.can_skip():
            raise _conflict(
                "SKIP_NOT_ALLOWED",
                "Solo se puede saltar una parada en camino o recién llegado (recepción).",
                status=order.status.value,
                service_step=order.service_step,
            )
        updated = await self.orders_repo.mark_skipped(
            id=order.id, reason=reason, note=note, at=datetime.now(timezone.utc),
        )
        # El cupo de ese día queda libre; al reprogramar, el admin asigna la nueva fecha a mano.
        await release_order_hold(self.holds_repo, updated)
        data = {"order_id": str(updated.id), "status": updated.status.value, "skip_reason": reason.value}
        motivo = _SKIP_REASON_TEXT[reason]
        await notify_user(
            self.orders_repo,
            user_id=updated.user_id,
            title="No pudimos atender tu servicio",
            body=f"Tu groomer no pudo completar la visita ({motivo}). Te contactaremos para reprogramarla.",
            data=data,
        )
        await _notify_admins(
            self.orders_repo, self.users_repo,
            title="Parada saltada",
            body=f"El groomer saltó una parada: {motivo}.",
            data=data,
        )
        return updated


@dataclass
class ReportDelay:
    orders_repo: object
    delays_repo: object
    users_repo: object

    async def execute(
        self, *, order_id: UUID, delay_minutes: int, note: Optional[str], actor_id: UUID, actor_role: str,
    ) -> DelayReport:
        order = await _load_for_groomer(self.orders_repo, order_id=order_id, actor_id=actor_id, actor_role=actor_role)
        if order.status not in _DELAY_STATUSES:
            raise _conflict("DELAY_NOT_ALLOWED", "Solo se avisa demora antes de llegar.", status=order.status.value)
        try:
            report = DelayReport.new(
                order_id=order.id, groomer_id=order.groomer_id or actor_id, delay_minutes=delay_minutes, note=note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        saved = await self.delays_repo.add(report)

        data = {"order_id": str(order.id), "delay_minutes": delay_minutes}
        await notify_user(
            self.orders_repo,
            user_id=order.user_id,
            title="Tu groomer viene con demora",
            body=f"Tu groomer llegará ~{delay_minutes} min más tarde.",
            data=data,
        )
        await _notify_admins(
            self.orders_repo, self.users_repo,
            title="Demora reportada",
            body=f"El groomer reportó ~{delay_minutes} min de demora.",
            data=data,
        )
        return saved


@dataclass
class ListDelayReports:
    orders_repo: object
    delays_repo: object

    async def execute(self, *, order_id: UUID, actor_id: UUID, actor_role: str) -> list[DelayReport]:
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if not (actor_role == "admin" or actor_id in (order.groomer_id, order.user_id)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta orden")
        return await self.delays_repo.list_by_order(order.id)
