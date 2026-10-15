"""
Peso de la mascota en la orden y saldo por diferencia (feature 0003-saldo-por-peso).

- Peso declarado: el que se usó al cotizar, guardado en `meta.pet_weight_kg` del servicio base.
- Peso medido: el que registra el groomer (o un admin) en el servicio. Si da un precio mayor, la orden
  guarda el monto extra; el admin genera luego el cobro (orden de ajuste). Si da uno igual o menor, solo
  se guarda el peso: no hay devoluciones.
- Saldo pendiente: suma de las órdenes de ajuste sin pagar. Con saldo, el cliente no pide servicios.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.app.use_cases_impl.groomer_view import declared_weight
from app.modules.orders.app.use_cases_impl.price_recalc import compute_price_check
from app.modules.orders.app.use_cases_impl.stops import _notify_admins
from app.modules.orders.app.use_cases_impl.transitions import notify_user
from app.modules.orders.domain.order import Order

logger = logging.getLogger(__name__)


def _fmt_kg(value: float) -> str:
    return f"{value:g} kg"


async def register_measured_weight(
    *,
    orders_repo,
    store_repo,
    users_repo,
    pet,
    weight_kg: float,
    actor_id: UUID,
    actor_role: str,
) -> Optional[dict[str, Any]]:
    """
    Registra el peso real en la orden que se está atendiendo (si la hay). Feature 0008 (decisión del
    cliente, BR-029): **no se cobra la diferencia**; el precio pagado se respeta y el peso real queda en
    el perfil para las próximas reservas. Devuelve siempre None (no hay monto por cobrar).
    """
    groomer_id = actor_id if actor_role == "groomer" else None
    order = await orders_repo.find_order_for_measurement(pet_id=pet.id, groomer_id=groomer_id)
    if order is None or order.adjustment_order_id is not None:
        return None
    await orders_repo.set_measured_weight(
        id=order.id, weight_kg=weight_kg, at=datetime.now(timezone.utc), extra_charge=None,
    )
    return None


async def _notify_extra_charge(orders_repo, users_repo, *, order: Order, pet, weight_kg: float) -> None:
    amount = f"{order.currency} {order.extra_charge:.2f}"
    declared = declared_weight(order)
    declared_txt = f" (declarado: {_fmt_kg(declared)})" if declared is not None else ""
    data = {"order_id": str(order.id), "extra_charge": order.extra_charge}

    await notify_user(
        orders_repo,
        user_id=order.user_id,
        title="Diferencia por peso",
        body=(
            f"{pet.name} pesó {_fmt_kg(weight_kg)}{declared_txt}. El servicio cuesta {amount} más; "
            "te avisaremos cuando el saldo esté listo para pagar."
        ),
        data=data,
        type="weight_difference",
    )
    if users_repo is not None:
        await _notify_admins(
            orders_repo,
            users_repo,
            title="Diferencia por peso por revisar",
            body=f"{pet.name}: {_fmt_kg(weight_kg)}{declared_txt} · {amount} por cobrar",
            data=data,
            type="weight_difference",
        )


async def pending_balance(orders_repo, *, user_id: UUID) -> tuple[float, str, list[Order]]:
    """(monto, moneda, órdenes de ajuste sin pagar) del cliente."""
    orders = await orders_repo.list_unpaid_adjustments(user_id=user_id)
    amount = round(sum(o.total_snapshot for o in orders), 2)
    currency = orders[0].currency if orders else "PEN"
    return amount, currency, orders


async def assert_no_pending_balance(orders_repo, *, user_id: UUID) -> None:
    """409 PENDING_BALANCE si el cliente tiene un saldo por pagar (no puede pedir otro servicio)."""
    amount, currency, orders = await pending_balance(orders_repo, user_id=user_id)
    if orders:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PENDING_BALANCE",
                "message": "Tienes un saldo pendiente por diferencia de peso. Págalo para pedir otro servicio.",
                "amount": amount,
                "currency": currency,
                "order_ids": [str(o.id) for o in orders],
            },
        )
