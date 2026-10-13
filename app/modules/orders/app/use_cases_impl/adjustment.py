"""
Órdenes de ajuste — cobro adicional cuando el peso real de la mascota (registrado en el servicio) da un
precio mayor al ya cobrado. El groomer solo registra el peso; el admin revisa y genera el cobro, una vez
por orden, por el monto guardado en `orders.extra_charge` (feature 0003-saldo-por-peso).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.app.use_cases_impl.groomer_view import order_pet_id
from app.modules.orders.app.use_cases_impl.transitions import notify_user
from app.modules.orders.domain.order import Order

logger = logging.getLogger(__name__)


def _conflict(code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": code, "message": message, **extra})


@dataclass
class CreateAdjustmentOrder:
    orders_repo: object  # PostgresOrderRepository

    async def execute(self, *, order_id: UUID, actor_role: str) -> Order:
        if actor_role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un admin genera el cobro")

        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if order.adjustment_order_id is not None:
            raise _conflict(
                "ADJUSTMENT_EXISTS",
                "Esta orden ya tiene su cobro por diferencia de peso.",
                adjustment_order_id=str(order.adjustment_order_id),
            )
        if not order.extra_charge or order.extra_charge <= 0:
            raise _conflict("NO_EXTRA_CHARGE", "No hay diferencia de precio que cobrar en esta orden.")

        pet_id = order_pet_id(order)
        adjustment = Order.new(
            user_id=order.user_id,
            items_snapshot=[{
                "kind": "price_adjustment",
                "ref_id": str(order.id),
                "name": "Ajuste por diferencia de peso",
                "qty": 1,
                "unit_price": order.extra_charge,
                "meta": {
                    "pet_id": str(pet_id) if pet_id else None,
                    "reason": "weight_recalculation",
                    "measured_weight_kg": order.measured_weight_kg,
                },
            }],
            total_snapshot=order.extra_charge,
            currency=order.currency,
            delivery_address_snapshot=order.delivery_address_snapshot,
            parent_order_id=order.id,
        )
        created = await self.orders_repo.create_order(adjustment)
        await self.orders_repo.set_adjustment_order(id=order.id, adjustment_order_id=created.id)
        if pet_id is not None:
            try:
                await self.orders_repo.add_order_pets(order_id=created.id, pet_ids=[pet_id])
            except Exception:
                logger.exception("No se pudo ligar la mascota al ajuste %s", created.id)

        await notify_user(
            self.orders_repo,
            user_id=order.user_id,
            title="Tienes un saldo por pagar",
            body=(
                f"Saldo de {order.currency} {order.extra_charge:.2f} por diferencia de peso. "
                "Págalo para poder pedir tu próximo servicio."
            ),
            data={"order_id": str(created.id), "parent_order_id": str(order.id)},
            type="pending_balance",
        )
        return created
