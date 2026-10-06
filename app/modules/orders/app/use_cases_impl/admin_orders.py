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
    holds_repo: Optional[object] = None         # C-21: mover el cupo si cambia el día
    availability_repo: Optional[object] = None

    async def _sync_reservation(self, order: Order, scheduled_at: datetime) -> Optional[object]:
        """
        Deja el cupo en el día de `scheduled_at` (hora de Lima). Devuelve la reserva nueva si se tomó
        una (y libera la anterior); None si el día no cambió o la orden no tiene servicio/mascota.
        Se ejecuta antes de tocar la orden: si el día está lleno (409 NO_CAPACITY) nada cambia.
        """
        from app.modules.booking.app.use_cases_impl.order_reservation import reserve_day_for_order
        from app.modules.booking.domain.hold import HoldStatus
        from app.modules.orders.app.use_cases_impl.groomer_view import base_item, order_pet_id

        if self.holds_repo is None or self.availability_repo is None:
            return None
        target_day = scheduled_at.astimezone(LIMA_TZ).date()

        current = await self.holds_repo.get_hold(order.hold_id) if order.hold_id else None
        vigente = current if current is not None and current.status == HoldStatus.confirmed else None
        if vigente is not None and vigente.date == target_day:
            return None  # mismo día: solo cambia la hora

        base = base_item(order)
        try:
            service_id = vigente.service_id if vigente else UUID(str((base or {}).get("ref_id")))
        except ValueError:
            return None
        pet_id = vigente.pet_id if vigente else order_pet_id(order)
        if pet_id is None:
            return None

        new_hold = await reserve_day_for_order(
            holds_repo=self.holds_repo,
            availability_repo=self.availability_repo,
            user_id=order.user_id,
            pet_id=pet_id,
            service_id=service_id,
            day=target_day,
        )
        if vigente is not None:
            await self.holds_repo.release(vigente.id)  # el día original recupera su cupo
        return new_hold

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

        # C-21: el cupo sigue al día asignado (antes de tocar nada: si está lleno → 409 NO_CAPACITY).
        new_hold = await self._sync_reservation(order, scheduled_at)
        if new_hold is not None:
            await self.orders_repo.set_reservation(id=order_id, hold_id=new_hold.id, reserved_date=new_hold.date)

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
