"""
Aviso a los admins de un pedido nuevo por asignar (C-20, pedido del front 2026-10-05).

Se dispara cuando una orden de servicio pasa a payment_status=paid por /pay (directo o reconciliado al
instante), por el cronjob de reconciliación o por confirm-payment. No aplica a:
  - órdenes de ajuste (parent_order_id): no se asignan;
  - confirm-cash-payment: lo usa un admin para pagos fuera de la pasarela; ya sabe del pedido.
El día es el reservado (todavía sin hora: la pone el admin al asignar).
"""
from __future__ import annotations

import logging
from typing import Optional

from app.modules.orders.app.use_cases_impl.groomer_notifications import _pet_name, _place
from app.modules.orders.app.use_cases_impl.groomer_view import base_item
from app.modules.orders.domain.order import Order

logger = logging.getLogger(__name__)


def _service_day(order: Order) -> Optional[str]:
    """Día reservado en ISO (reserved_date, o meta.scheduled_date del servicio base)."""
    if order.reserved_date is not None:
        return order.reserved_date.isoformat()
    meta = (base_item(order) or {}).get("meta") or {}
    return str(meta["scheduled_date"]) if meta.get("scheduled_date") else None


async def notify_admins_order_paid(orders_repo, order: Order, *, users_repo=None, pets_repo=None) -> None:
    """Best-effort: nunca rompe el flujo de pago."""
    if order.parent_order_id is not None:
        return
    try:
        from app.core.db import engine
        from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository
        from app.modules.orders.app.use_cases_impl.stops import _notify_admins
        from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository

        session = orders_repo._session
        users_repo = users_repo or PostgresUserRepository(session=session, engine=engine)
        pets_repo = pets_repo or PostgresPetRepository(session=session, engine=engine)

        day_iso = _service_day(order)
        day_txt = f"{day_iso[8:10]}/{day_iso[5:7]}" if day_iso else "sin fecha"
        parts = [await _pet_name(pets_repo, order), (base_item(order) or {}).get("name") or "Servicio", day_txt]
        place = _place(order)
        if place:
            parts.append(place)

        await _notify_admins(
            orders_repo,
            users_repo,
            title="Nuevo pedido por asignar",
            body=" · ".join(parts),
            data={"order_id": str(order.id), "scheduled_date": day_iso},
            type="order_paid",
        )
    except Exception:
        logger.exception("No se pudo avisar a los admins del pedido pagado %s", order.id)
