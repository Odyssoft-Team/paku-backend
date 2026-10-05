"""
Use cases administrativos para la gestión de órdenes:
asignación de groomer, listado con filtros y consulta individual.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.timezone import LIMA_TZ
from app.modules.orders.app.use_cases_impl.groomer_notifications import notify_groomer_assignment
from app.modules.orders.domain.assignment import OrderAssignment
from app.modules.orders.domain.order import Order, OrderStatus
from app.modules.orders.infra.postgres_order_assignment_repository import PostgresOrderAssignmentRepository
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# AssignOrder — admin asigna un groomer y programa la fecha/hora
# ------------------------------------------------------------------

@dataclass
class AssignOrder:
    orders_repo: PostgresOrderRepository
    assignments_repo: PostgresOrderAssignmentRepository
    pets_repo: Optional[object] = None  # para el nombre de la mascota en la notificación al groomer

    async def execute(
        self,
        *,
        order_id: UUID,
        groomer_id: UUID,
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
            groomer_id=groomer_id,
            scheduled_at=scheduled_at,
            assigned_by=assigned_by,
            notes=notes,
        )
        await self.assignments_repo.create(assignment)

        # Reprogramar una parada saltada (pedido 4): vuelve a created y el proceso del servicio
        # empieza de cero. El motivo del salto se conserva como historial.
        if order.status == OrderStatus.skipped:
            await self.orders_repo.set_status(id=order_id, status=OrderStatus.created)
            await self.orders_repo.set_service_step(id=order_id, step=None, at=datetime.now(timezone.utc))

        # Actualizar datos desnormalizados en la orden para queries rápidas
        updated_order = await self.orders_repo.set_groomer(
            id=order_id,
            groomer_id=groomer_id,
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
                # En hora de Lima: scheduled_at llega en UTC ("…Z") y se mostraba 5 h adelantado.
                body=f"Tu servicio fue programado. Tu groomer estará contigo el {scheduled_at.astimezone(LIMA_TZ).strftime('%d/%m/%Y a las %H:%M')}.",
                data={"order_id": str(order_id), "scheduled_at": scheduled_at.isoformat()},
            )
        except Exception as exc:
            logger.exception("Failed to send assignment notification: %s", exc)

        # Notificar al groomer (C-17): nueva parada, reprogramación o retiro de su ruta.
        await notify_groomer_assignment(self.orders_repo, self.pets_repo, before=order, after=updated_order)

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
        groomer_id: Optional[UUID] = None,
    ) -> list[Order]:
        return await self.orders_repo.list_orders_admin(status=status, groomer_id=groomer_id)


# ------------------------------------------------------------------
# ListGroomerOrders — órdenes asignadas al groomer autenticado
# ------------------------------------------------------------------



def lima_day_range(day: date) -> tuple[datetime, datetime]:
    """[inicio, fin) del día `day` en hora de Lima, como datetimes con zona."""
    start = datetime(day.year, day.month, day.day, tzinfo=LIMA_TZ)
    return start, start + timedelta(days=1)


@dataclass
class ListGroomerOrders:
    orders_repo: PostgresOrderRepository

    async def execute(
        self,
        *,
        groomer_id: UUID,
        status: Optional[OrderStatus] = None,
        day: Optional[date] = None,
    ) -> list[Order]:
        """Ruta del groomer en orden de scheduled_at (lo define el admin); `day` filtra en hora de Lima."""
        scheduled_from = scheduled_to = None
        if day is not None:
            scheduled_from, scheduled_to = lima_day_range(day)
        return await self.orders_repo.list_orders_by_groomer(
            groomer_id=groomer_id, status=status, scheduled_from=scheduled_from, scheduled_to=scheduled_to,
        )


@dataclass
class GetGroomerOrder:
    """Una parada del groomer: solo la orden que tiene asignada (admin ve cualquiera)."""
    orders_repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, groomer_id: UUID, role: str) -> Order:
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if role != "admin" and order.groomer_id != groomer_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta orden")
        return order
