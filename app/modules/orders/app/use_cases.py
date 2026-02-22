from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.domain.order import Order, OrderStatus
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.cart.infra.postgres_cart_repository import PostgresCartRepository


def _snapshot_cart_items(items: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in items:
        out.append(
            {
                "id": str(getattr(i, "id")),
                "cart_id": str(getattr(i, "cart_id")),
                "kind": getattr(getattr(i, "kind", None), "value", getattr(i, "kind", None)),
                "ref_id": str(getattr(i, "ref_id")),
                "name": getattr(i, "name", None),
                "qty": int(getattr(i, "qty", 1)),
                "unit_price": getattr(i, "unit_price", None),
                "meta": getattr(i, "meta", None),
            }
        )
    return out


def _calc_total(items: list[Any]) -> float:
    total = 0.0
    for i in items:
        unit_price = getattr(i, "unit_price", None)
        if unit_price is None:
            continue
        total += float(unit_price) * int(getattr(i, "qty", 1))
    return total


@dataclass
class CreateOrderFromCart:
    orders_repo: PostgresOrderRepository
    cart_repo: PostgresCartRepository

    async def execute(self, *, user_id: UUID, cart_id: UUID, delivery_address_snapshot: dict) -> Order:
        from app.modules.cart.domain.cart import CartStatus
        from app.core.db import engine
        from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
        from app.modules.notifications.app.use_cases import CreateNotification

        cart = await self.cart_repo.get_cart(cart_id=cart_id, user_id=user_id)
        if cart.status != CartStatus.checked_out:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart must be checked_out")

        items = await self.cart_repo.list_items(cart_id=cart_id, user_id=user_id)
        items_snapshot = _snapshot_cart_items(items)
        total_snapshot = _calc_total(items)

        order = Order.new(
            user_id=user_id,
            items_snapshot=items_snapshot,
            total_snapshot=total_snapshot,
            currency="PEN",
            delivery_address_snapshot=delivery_address_snapshot,
        )
        created = await self.orders_repo.create_order(order)

        # Crear notificación (best effort, no bloquea la orden)
        try:
            notifications_repo = PostgresNotificationRepository(session=self.orders_repo._session, engine=engine)
            await CreateNotification(repo=notifications_repo).execute(
                user_id=user_id,
                type="order_status",
                title="Pedido creado",
                body="Tu pedido fue creado y está en preparación.",
                data={"order_id": str(created.id), "status": created.status.value},
            )
        except Exception as exc:
            import logging
            logging.exception("Failed to create order notification: %s", exc)

        return created


@dataclass
class ListOrders:
    orders_repo: PostgresOrderRepository

    async def execute(self, *, user_id: UUID) -> list[Order]:
        return await self.orders_repo.list_orders(user_id=user_id)


@dataclass
class GetOrder:
    orders_repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, user_id: UUID) -> Order:
        try:
            return await self.orders_repo.get_order(id=order_id, user_id=user_id)
        except ValueError as exc:
            if str(exc) == "order_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from exc
            raise


def _status_message(status_value: str) -> tuple[str, str]:
    if status_value == OrderStatus.in_process.value:
        return ("Pedido en proceso", "Tu pedido está siendo preparado.")
    if status_value == OrderStatus.on_the_way.value:
        return ("Pedido en camino", "Tu pedido ya salió y está en camino.")
    if status_value == OrderStatus.delivered.value:
        return ("Pedido entregado", "Tu pedido fue entregado.")
    return ("Estado de pedido actualizado", "Se actualizó el estado de tu pedido.")


@dataclass
class UpdateOrderStatus:
    orders_repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, status: OrderStatus) -> Order:
        from app.core.db import engine
        from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
        from app.modules.notifications.app.use_cases import CreateNotification

        try:
            existing = await self.orders_repo.get_order_admin(id=order_id)
            if existing is None:
                raise ValueError("order_not_found")

            updated = await self.orders_repo.update_status(id=order_id, status=status)
        except ValueError as exc:
            if str(exc) == "order_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from exc
            if str(exc) == "invalid_status_transition":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invalid status transition",
                ) from exc
            raise

        title, body = _status_message(updated.status.value)
        
        # Crear notificación (best effort, no bloquea la actualización)
        try:
            notifications_repo = PostgresNotificationRepository(session=self.orders_repo._session, engine=engine)
            await CreateNotification(repo=notifications_repo).execute(
                user_id=updated.user_id,
                type="order_status",
                title=title,
                body=body,
                data={"order_id": str(updated.id), "status": updated.status.value},
            )
        except Exception as exc:
            import logging
            logging.exception("Failed to create order status notification: %s", exc)

        return updated


@dataclass
class PatchOrder:
    orders_repo: PostgresOrderRepository

    async def execute(self, *, order_id: UUID, user_id: UUID, status: Optional[OrderStatus] = None) -> Order:
        if status is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field must be provided for patch"
            )

        try:
            # Verificar que la orden exista y pertenezca al usuario
            existing = await self.orders_repo.get_order(id=order_id, user_id=user_id)
            if existing is None:
                raise ValueError("order_not_found")

            # Validar transición de estado
            if not existing.can_advance_to(status):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot transition from {existing.status.value} to {status.value}"
                )

            # Actualizar estado
            updated = await self.orders_repo.update_status(id=order_id, status=status)
            
        except ValueError as exc:
            if str(exc) == "order_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from exc
            if str(exc) == "invalid_status_transition":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invalid status transition",
                ) from exc
            raise

        # Crear notificación para el usuario
        from app.core.db import engine
        from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
        from app.modules.notifications.app.use_cases import CreateNotification

        title, body = _status_message(updated.status.value)
        
        # Crear notificación (best effort, no bloquea la actualización)
        try:
            notifications_repo = PostgresNotificationRepository(session=self.orders_repo._session, engine=engine)
            await CreateNotification(repo=notifications_repo).execute(
                user_id=updated.user_id,
                type="order_status",
                title=title,
                body=body,
                data={"order_id": str(updated.id), "status": updated.status.value},
            )
        except Exception as exc:
            import logging
            logging.exception("Failed to create order status notification: %s", exc)
        
        return updated
