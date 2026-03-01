from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4


# [TECH]
# Immutable entity representing the assignment of an ally to an order.
#
# [NATURAL/BUSINESS]
# Registro que el administrador crea cuando asigna un groomer/ally a una orden
# y define la fecha y hora programada del servicio. Permite historial de
# reasignaciones: cada asignación nueva es un registro distinto.
@dataclass(frozen=True)
class OrderAssignment:
    id: UUID
    order_id: UUID
    ally_id: UUID          # groomer/ally asignado
    scheduled_at: datetime # fecha y hora programada del servicio (ej: viernes 4pm)
    assigned_by: UUID      # admin que realizó la asignación
    notes: Optional[str]
    created_at: datetime

    @staticmethod
    def new(
        *,
        order_id: UUID,
        ally_id: UUID,
        scheduled_at: datetime,
        assigned_by: UUID,
        notes: Optional[str] = None,
    ) -> "OrderAssignment":
        now = datetime.now(timezone.utc)
        return OrderAssignment(
            id=uuid4(),
            order_id=order_id,
            ally_id=ally_id,
            scheduled_at=scheduled_at,
            assigned_by=assigned_by,
            notes=notes,
            created_at=now,
        )
