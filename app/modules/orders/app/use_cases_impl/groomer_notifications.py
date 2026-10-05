"""
Notificaciones al groomer (pedido C-17 del front, 2026-10-05).

Lo que el admin cambia en la ruta del groomer (asignar, reprogramar, reasignar, cancelar) le llega como
notificación + push (best-effort, vía `notify_user`). Lo que el propio groomer dispara (depart, arrive,
next-step, skip, delay-report) no se le notifica.

Tipos (para el ícono y la navegación en la app Groomer; `data.order_id` abre el detalle):
  order_assigned · order_rescheduled · order_unassigned · order_cancelled
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.core.timezone import LIMA_TZ
from app.modules.orders.app.use_cases_impl.groomer_view import order_pet_id
from app.modules.orders.app.use_cases_impl.transitions import notify_user
from app.modules.orders.domain.order import Order


def _when(scheduled_at: Optional[datetime]) -> str:
    """dd/mm HH:MM en hora de Lima."""
    if scheduled_at is None:
        return "sin fecha"
    return scheduled_at.astimezone(LIMA_TZ).strftime("%d/%m %H:%M")


def _place(order: Order) -> Optional[str]:
    """Distrito del domicilio (o la dirección si el distrito no está en el catálogo)."""
    from app.modules.geo.infra.districts_data import get_district_by_id

    address = order.delivery_address_snapshot or {}
    district = get_district_by_id(str(address.get("district_id"))) if address.get("district_id") else None
    if district and district.get("name"):
        return district["name"]
    return address.get("address_line")


async def _pet_name(pets_repo, order: Order) -> str:
    pet_id = order_pet_id(order)
    if pets_repo is not None and pet_id is not None:
        try:
            pet = await pets_repo.get_by_id(pet_id, include_deleted=True)
            if pet is not None and pet.name:
                return pet.name
        except Exception:
            pass
    return "Mascota"


async def notify_groomer_assignment(orders_repo, pets_repo, *, before: Order, after: Order) -> None:
    """
    Tras POST /admin/orders/{id}/assign:
      - groomer nuevo (no tenía, o cambió) → al nuevo "Nueva parada asignada" (order_assigned);
        si cambió → al anterior "Parada retirada de tu ruta" (order_unassigned).
      - mismo groomer y cambia la fecha, o la parada venía de skipped → "Parada reprogramada" (order_rescheduled).
    """
    if after.groomer_id is None:
        return
    pet = await _pet_name(pets_repo, after)
    data = {
        "order_id": str(after.id),
        "status": after.status.value,
        "scheduled_at": after.scheduled_at.isoformat() if after.scheduled_at else None,
    }

    if before.groomer_id != after.groomer_id:
        place = _place(after)
        body = f"{pet} · {_when(after.scheduled_at)}" + (f" · {place}" if place else "")
        await notify_user(
            orders_repo, user_id=after.groomer_id, type="order_assigned",
            title="Nueva parada asignada", body=body, data=data,
        )
        if before.groomer_id is not None:
            await notify_user(
                orders_repo, user_id=before.groomer_id, type="order_unassigned",
                title="Parada retirada de tu ruta",
                body=f"{pet} · {_when(before.scheduled_at)} fue asignada a otro groomer",
                data={"order_id": str(after.id)},
            )
        return

    from app.modules.orders.domain.order import OrderStatus

    if before.scheduled_at != after.scheduled_at or before.status == OrderStatus.skipped:
        await notify_user(
            orders_repo, user_id=after.groomer_id, type="order_rescheduled",
            title="Parada reprogramada", body=f"{pet} pasa al {_when(after.scheduled_at)}", data=data,
        )


async def notify_groomer_cancelled(orders_repo, pets_repo, order: Order) -> None:
    """Tras POST /admin/orders/{id}/cancel, si la orden tenía groomer."""
    if order.groomer_id is None:
        return
    pet = await _pet_name(pets_repo, order)
    await notify_user(
        orders_repo, user_id=order.groomer_id, type="order_cancelled",
        title="Parada cancelada", body=f"{pet} · {_when(order.scheduled_at)} fue cancelada",
        data={"order_id": str(order.id), "status": "cancelled"},
    )
