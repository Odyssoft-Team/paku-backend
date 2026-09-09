from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


# [TECH]
# Enum defining order lifecycle states with ordinal mapping.
#
# [NATURAL/BUSINESS]
# Estados por los que pasa un servicio a domicilio, en orden cronológico:
# creado → aceptado por ally → ally en camino → servicio iniciado → finalizado.
# cancelled es una rama alternativa que puede ocurrir desde cualquier estado activo.
class OrderStatus(str, Enum):
    created    = "created"     # reserva confirmada, pendiente de asignación
    accepted   = "accepted"    # ally aceptó (reservado para futuro)
    on_the_way = "on_the_way"  # ally salió hacia el domicilio
    in_service = "in_service"  # ally llegó, servicio en curso
    done       = "done"        # servicio finalizado
    cancelled  = "cancelled"   # cancelado (rama alternativa)


# [TECH]
# Enum tracking the payment lifecycle independently from the service lifecycle.
#
# [NATURAL/BUSINESS]
# Estado del cobro asociado a la orden. Es independiente del estado del servicio:
# una orden puede estar "created" (servicio no iniciado) pero "paid" (ya cobrada).
# pending    → orden creada, aún no se intentó cobrar
# verifying  → se intentó cobrar pero la respuesta (de culqi-python o de nuestra propia
#              reconciliación) no llegó a tiempo; el cronjob de reconciliación sigue
#              reintentando hasta resolver a paid/failed o escalar tras 15-20 minutos
# paid       → cobro confirmado; culqi_charge_id presente (o payment_method=cash confirmado
#              por el ally)
# failed     → el cobro fue rechazado por Culqi; la orden no debe procesarse
class PaymentStatus(str, Enum):
    pending   = "pending"
    verifying = "verifying"
    paid      = "paid"
    failed    = "failed"


# [NATURAL/BUSINESS]
# Cómo se pagó la orden. "card"/"yape" pasan por Culqi (culqi_charge_id presente);
# "cash" se confirma directo por el ally al momento de la entrega, sin pasar por Culqi.
class PaymentMethod(str, Enum):
    card = "card"
    yape = "yape"
    cash = "cash"


# [TECH]
# Ordinal mapping for forward-only transition validation.
# cancelled no tiene ordinal: puede ocurrir desde cualquier estado activo.
#
# [NATURAL/BUSINESS]
# Define el orden correcto del flujo principal del servicio.
_STATUS_ORDER: dict[OrderStatus, int] = {
    OrderStatus.created:    1,
    OrderStatus.accepted:   2,
    OrderStatus.on_the_way: 3,
    OrderStatus.in_service: 4,
    OrderStatus.done:       5,
}

# Estados desde los que se puede cancelar
_CANCELLABLE_STATUSES: frozenset[OrderStatus] = frozenset({
    OrderStatus.created,
    OrderStatus.accepted,
    OrderStatus.on_the_way,
})


# [TECH]
# Immutable order entity with ally assignment, scheduling, and payment fields.
#
# [NATURAL/BUSINESS]
# Pedido de servicio a domicilio. Incluye quién lo hace (ally_id) y
# cuándo está programado (scheduled_at), que se pueblan al asignar.
# El pago se registra via payment_status y culqi_charge_id cuando el
# frontend confirma el cargo exitoso desde culqi-python.
@dataclass(frozen=True)
class Order:
    id: UUID
    user_id: UUID
    status: OrderStatus
    items_snapshot: Any
    total_snapshot: float
    currency: str
    delivery_address_snapshot: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    ally_id: Optional[UUID] = None           # quién realiza el servicio
    scheduled_at: Optional[datetime] = None  # fecha/hora programada del servicio
    hold_id: Optional[UUID] = None           # reserva que originó esta orden
    payment_status: PaymentStatus = PaymentStatus.pending  # estado del cobro en Culqi
    culqi_charge_id: Optional[str] = None   # chr_(test|live)_XXXXXXXXXXXXXXXX de Culqi
    payment_method: Optional[PaymentMethod] = None  # card | yape | cash; None hasta que se paga
    parent_order_id: Optional[UUID] = None  # presente solo en "órdenes de ajuste" por recálculo

    # [TECH]
    # Factory creating Order with created status and timestamps.
    #
    # [NATURAL/BUSINESS]
    # Crea una orden nueva en estado inicial. ally_id y scheduled_at
    # se asignan luego por el administrador.
    @staticmethod
    def new(
        *,
        user_id: UUID,
        items_snapshot: Any,
        total_snapshot: float,
        currency: str = "PEN",
        delivery_address_snapshot: Optional[dict[str, Any]] = None,
        hold_id: Optional[UUID] = None,
        parent_order_id: Optional[UUID] = None,
    ) -> "Order":
        now = datetime.now(timezone.utc)
        return Order(
            id=uuid4(),
            user_id=user_id,
            status=OrderStatus.created,
            parent_order_id=parent_order_id,
            items_snapshot=items_snapshot,
            total_snapshot=total_snapshot,
            currency=currency,
            delivery_address_snapshot=delivery_address_snapshot,
            created_at=now,
            updated_at=now,
            hold_id=hold_id,
            payment_status=PaymentStatus.pending,
            culqi_charge_id=None,
        )

    # [TECH]
    # Validates forward-only transitions on the main flow.
    # cancelled is handled separately via can_cancel().
    #
    # [NATURAL/BUSINESS]
    # Verifica si el pedido puede avanzar al siguiente estado del flujo principal.
    def can_advance_to(self, new_status: OrderStatus) -> bool:
        if new_status == OrderStatus.cancelled:
            return False  # usar can_cancel()
        if new_status not in _STATUS_ORDER or self.status not in _STATUS_ORDER:
            return False
        return _STATUS_ORDER[new_status] > _STATUS_ORDER[self.status]

    # [TECH]
    # Validates whether the order can be cancelled from its current state.
    #
    # [NATURAL/BUSINESS]
    # Solo se puede cancelar antes de que el servicio comience (in_service o done).
    def can_cancel(self) -> bool:
        return self.status in _CANCELLABLE_STATUSES
