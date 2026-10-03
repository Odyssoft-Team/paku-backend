"""
Proceso del servicio en la van (pedido 3) y fotos de la orden (pedido 6).

Pasos fijos: reception → bath → drying → finishing → return (ver `SERVICE_STEPS`).
- /arrive deja la orden en "reception".
- /next-step avanza un paso (con `from_step` para que un doble tap no avance dos veces).
  · desde "reception" exige una foto `initial`;
  · desde "finishing" exige que todos los addons comprados estén realizados;
  · "return" se cierra con /complete.
- Los addons comprados se marcan como realizados en bath / drying / finishing, en cualquier orden.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.app.use_cases_impl.groomer_view import purchased_addons
from app.modules.orders.app.use_cases_impl.transitions import notify_user
from app.modules.orders.domain.order import (
    ADDON_STEPS,
    SERVICE_STEP_LABELS,
    SERVICE_STEPS,
    Order,
    OrderStatus,
    next_service_step,
)
from app.modules.orders.domain.photo import OrderPhoto, OrderPhotoKind


def _conflict(code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": code, "message": message, **extra})


async def _load_for_groomer(orders_repo, *, order_id: UUID, actor_id: UUID, actor_role: str) -> Order:
    """La orden, si quien llama es su groomer asignado o un admin."""
    order = await orders_repo.get_order_admin(id=order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if actor_role != "admin" and order.groomer_id != actor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta orden")
    return order


def _done_addon_ids(order: Order) -> set[str]:
    return {str(a.get("addon_id")) for a in (order.addons_done or [])}


@dataclass
class NextServiceStep:
    orders_repo: object
    photos_repo: object

    async def execute(self, *, order_id: UUID, from_step: str, actor_id: UUID, actor_role: str) -> Order:
        order = await _load_for_groomer(self.orders_repo, order_id=order_id, actor_id=actor_id, actor_role=actor_role)
        if order.status != OrderStatus.in_service:
            raise _conflict("NOT_IN_SERVICE", "La orden no está en servicio.", status=order.status.value)
        if from_step != order.service_step:
            raise _conflict(
                "STEP_MISMATCH",
                "El paso indicado no es el paso actual (¿doble envío?).",
                service_step=order.service_step,
            )
        if from_step not in SERVICE_STEPS:
            raise _conflict("UNKNOWN_STEP", "Paso desconocido.", service_step=order.service_step)

        target = next_service_step(from_step)
        if target is None:
            raise _conflict("LAST_STEP", "La devolución se cierra con /complete.", service_step=from_step)

        if from_step == "reception" and not await self.photos_repo.has_kind(order.id, OrderPhotoKind.initial):
            raise _conflict("INITIAL_PHOTO_REQUIRED", "Falta la foto inicial de la mascota.")

        if from_step == "finishing":
            done = _done_addon_ids(order)
            pending = [a for a in purchased_addons(order) if a["id"] not in done]
            if pending:
                raise _conflict("ADDONS_PENDING", "Faltan complementos por realizar.", addons=pending)

        updated = await self.orders_repo.set_service_step(id=order.id, step=target, at=datetime.now(timezone.utc))
        label = SERVICE_STEP_LABELS[target]
        await notify_user(
            self.orders_repo,
            user_id=updated.user_id,
            title=label,
            body=f"Tu mascota está en: {label}.",
            data={"order_id": str(updated.id), "status": updated.status.value, "service_step": target},
        )
        return updated


@dataclass
class MarkAddonDone:
    orders_repo: object

    async def execute(self, *, order_id: UUID, addon_id: str, actor_id: UUID, actor_role: str) -> Order:
        order = await _load_for_groomer(self.orders_repo, order_id=order_id, actor_id=actor_id, actor_role=actor_role)
        addon = next((a for a in purchased_addons(order) if a["id"] == str(addon_id)), None)
        if addon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El complemento no está en la orden")
        if order.status != OrderStatus.in_service or order.service_step not in ADDON_STEPS:
            raise _conflict(
                "ADDON_NOT_ALLOWED_NOW",
                "Los complementos se marcan durante baño, secado o corte y acabado.",
                service_step=order.service_step,
            )
        if str(addon_id) in _done_addon_ids(order):
            return order  # idempotente: no duplica ni vuelve a notificar

        updated = await self.orders_repo.mark_addon_done(id=order.id, addon_id=str(addon_id), at=datetime.now(timezone.utc))
        name = addon.get("name") or "Complemento"
        await notify_user(
            self.orders_repo,
            user_id=updated.user_id,
            title=f"{name} realizado",
            body=f"{name} realizado.",
            data={"order_id": str(updated.id), "addon_id": str(addon_id)},
        )
        return updated


@dataclass
class AddOrderPhoto:
    orders_repo: object
    photos_repo: object

    async def execute(
        self,
        *,
        order_id: UUID,
        object_name: str,
        kind: OrderPhotoKind,
        note: Optional[str],
        actor_id: UUID,
        actor_role: str,
    ) -> OrderPhoto:
        from app.media.gcs import parse_object_name

        order = await _load_for_groomer(self.orders_repo, order_id=order_id, actor_id=actor_id, actor_role=actor_role)
        try:
            prefix, entity_id = parse_object_name(object_name)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if prefix != "orders" or entity_id != order.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="object_name does not belong to this order",
            )
        photo = OrderPhoto.new(order_id=order.id, kind=kind, object_name=object_name, uploaded_by=actor_id, note=note)
        return await self.photos_repo.add(photo)


@dataclass
class ListOrderPhotos:
    orders_repo: object
    photos_repo: object

    async def execute(self, *, order_id: UUID, actor_id: UUID, actor_role: str) -> list[OrderPhoto]:
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        allowed = actor_role == "admin" or order.groomer_id == actor_id or order.user_id == actor_id
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta orden")
        return await self.photos_repo.list_by_order(order.id)
