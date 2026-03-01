"""
Use cases administrativos para la gestión de órdenes:
asignación de ally, listado con filtros y consulta individual.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.domain.assignment import OrderAssignment
from app.modules.orders.domain.order import Order, OrderStatus
from app.modules.orders.infra.postgres_order_assignment_repository import PostgresOrderAssignmentRepository
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# AssignOrder — admin asigna un ally y programa la fecha/hora
# ------------------------------------------------------------------

@dataclass
class AssignOrder:
    orders_repo: PostgresOrderRepository
    assignments_repo: PostgresOrderAssignmentRepository

    async def execute(
        self,
        *,
        order_id: UUID,
        ally_id: UUID,
        scheduled_at: datetime,
        assigned_by: UUID,
        notes: Optional[str] = None,
    ) -> tuple[Order, OrderAssignment]:
        # Verificar que la orden existe
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        # No se puede asignar una orden cancelada o finalizada
        if order.status in (OrderStatus.cancelled, OrderStatus.done):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"assign_invalid: no se puede asignar una orden en estado '{order.status.value}'",
            )

        # Crear registro de asignación (historial)
        assignment = OrderAssignment.new(
            order_id=order_id,
            ally_id=ally_id,
            scheduled_at=scheduled_at,
            assigned_by=assigned_by,
            notes=notes,
        )
        await self.assignments_repo.create(assignment)

        # Actualizar datos desnormalizados en la orden para queries rápidas
        updated_order = await self.orders_repo.set_ally(
            id=order_id,
            ally_id=ally_id,
            scheduled_at=scheduled_at,
        )

        # Notificar al cliente (best effort)
        try:
            from app.core.db import engine
            from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
            from app.modules.notifications.app.use_cases import CreateNotification

            notifications_repo = PostgresNotificationRepository(
                session=self.orders_repo._session, engine=engine
            )
            await CreateNotification(repo=notifications_repo).execute(
                user_id=updated_order.user_id,
                type="order_assigned",
                title="Servicio asignado",
                body=f"Tu servicio fue programado. Tu groomer estará contigo el {scheduled_at.strftime('%d/%m/%Y a las %H:%M')}.",
                data={"order_id": str(order_id), "scheduled_at": scheduled_at.isoformat()},
            )
        except Exception as exc:
            logger.exception("Failed to send assignment notification: %s", exc)

        return updated_order, assignment


# ------------------------------------------------------------------
# GetOrderAdmin — obtener cualquier orden sin restricción de user_id
# ------------------------------------------------------------------

@dataclass
class GetOrderAdmin:
    orders_repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID) -> Order:
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return order


# ------------------------------------------------------------------
# ListOrdersAdmin — listar órdenes con filtros opcionales
# ------------------------------------------------------------------

@dataclass
class ListOrdersAdmin:
    orders_repo: PostgresOrderRepository

    async def execute(
        self,
        *,
        status: Optional[OrderStatus] = None,
        ally_id: Optional[UUID] = None,
    ) -> list[Order]:
        return await self.orders_repo.list_orders_admin(status=status, ally_id=ally_id)


# ------------------------------------------------------------------
# ListAllyOrders — órdenes asignadas al ally autenticado
# ------------------------------------------------------------------

@dataclass
class ListAllyOrders:
    orders_repo: PostgresOrderRepository

    async def execute(
        self,
        *,
        ally_id: UUID,
        status: Optional[OrderStatus] = None,
    ) -> list[Order]:
        return await self.orders_repo.list_orders_by_ally(ally_id=ally_id, status=status)
