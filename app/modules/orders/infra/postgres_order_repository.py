from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.orders.domain.order import Order, OrderStatus, PaymentMethod, PaymentStatus, SkipReason


class PostgresOrderRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def _ensure_ready(self) -> None:
        from app.modules.orders.infra.models import ensure_orders_schema
        await ensure_orders_schema(self._engine)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_order(r) -> Order:
        return Order(
            id=r.id,
            user_id=r.user_id,
            status=OrderStatus(r.status),
            items_snapshot=r.items_snapshot,
            total_snapshot=float(r.total_snapshot),
            currency=r.currency,
            delivery_address_snapshot=r.delivery_address_snapshot,
            created_at=r.created_at,
            updated_at=r.updated_at,
            groomer_id=r.groomer_id,
            scheduled_at=r.scheduled_at,
            hold_id=r.hold_id,
            reserved_date=r.reserved_date,
            payment_status=PaymentStatus(r.payment_status),
            culqi_charge_id=r.culqi_charge_id,
            payment_method=PaymentMethod(r.payment_method) if r.payment_method else None,
            parent_order_id=r.parent_order_id,
            service_step=r.service_step,
            service_steps_log=list(r.service_steps_log or []),
            addons_done=list(r.addons_done or []),
            skip_reason=SkipReason(r.skip_reason) if r.skip_reason else None,
            skip_note=r.skip_note,
            skipped_at=r.skipped_at,
        )

    async def set_reservation(self, *, id: UUID, hold_id: Optional[UUID], reserved_date) -> Order:
        """Actualiza la reserva de cupo de la orden. hold_id=None conserva el anterior (historial)."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        if hold_id is not None:
            model.hold_id = hold_id
        model.reserved_date = reserved_date
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def mark_skipped(self, *, id: UUID, reason: SkipReason, note: Optional[str], at: datetime) -> Order:
        """La parada se saltó: status=skipped y motivo (el paso del servicio se conserva)."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        model.status = OrderStatus.skipped.value
        model.skip_reason = reason.value
        model.skip_note = note
        model.skipped_at = at
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def set_service_step(self, *, id: UUID, step: Optional[str], at: datetime) -> Order:
        """Fija el paso actual del servicio y lo agrega a la bitácora (step=None limpia todo)."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        if step is None:
            model.service_step = None
            model.service_steps_log = None
            model.addons_done = None
        else:
            model.service_step = step
            # Lista nueva (no append) para que SQLAlchemy detecte el cambio en la columna JSON.
            model.service_steps_log = list(model.service_steps_log or []) + [
                {"step": step, "started_at": at.isoformat()}
            ]
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def mark_addon_done(self, *, id: UUID, addon_id: str, at: datetime) -> Order:
        """Agrega el addon a addons_done (el use case evita duplicados)."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        model.addons_done = list(model.addons_done or []) + [{"addon_id": addon_id, "done_at": at.isoformat()}]
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def create_order(self, order: Order) -> Order:
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = OrderModel(
            id=order.id,
            user_id=order.user_id,
            status=order.status.value,
            items_snapshot=order.items_snapshot,
            total_snapshot=Decimal(str(order.total_snapshot)),
            currency=order.currency,
            delivery_address_snapshot=order.delivery_address_snapshot,
            groomer_id=order.groomer_id,
            scheduled_at=order.scheduled_at,
            hold_id=order.hold_id,
            reserved_date=order.reserved_date,
            payment_status=order.payment_status.value,
            culqi_charge_id=order.culqi_charge_id,
            parent_order_id=order.parent_order_id,
            created_at=order.created_at,
            updated_at=utcnow(),
        )
        self._session.add(model)
        await self._session.commit()
        return order

    async def create_order_in_tx(self, order: Order) -> Order:
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = OrderModel(
            id=order.id,
            user_id=order.user_id,
            status=order.status.value,
            items_snapshot=order.items_snapshot,
            total_snapshot=Decimal(str(order.total_snapshot)),
            currency=order.currency,
            delivery_address_snapshot=order.delivery_address_snapshot,
            groomer_id=order.groomer_id,
            scheduled_at=order.scheduled_at,
            hold_id=order.hold_id,
            reserved_date=order.reserved_date,
            payment_status=order.payment_status.value,
            culqi_charge_id=order.culqi_charge_id,
            parent_order_id=order.parent_order_id,
            created_at=order.created_at,
            updated_at=utcnow(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return order

    async def add_order_pets(self, *, order_id: UUID, pet_ids: list[UUID]) -> None:
        """
        Puebla la tabla puente order_pets con los pet_id únicos de la orden (extraídos de
        items_snapshot[].meta.pet_id por el llamador). Permite luego consultar "¿qué orden
        tiene esta mascota?" sin parsear JSON.
        """
        from app.modules.orders.infra.models import OrderPetModel
        await self._ensure_ready()
        for pet_id in dict.fromkeys(pet_ids):  # dedup preservando orden
            self._session.add(OrderPetModel(order_id=order_id, pet_id=pet_id))
        await self._session.commit()

    async def update_status(self, *, id: UUID, status: OrderStatus) -> Order:
        """Avanza el estado validando la transición (mantiene compatibilidad con use cases existentes)."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        current_order = self._row_to_order(model)
        if not current_order.can_advance_to(status):
            raise ValueError("invalid_status_transition")
        model.status = status.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def set_status(self, *, id: UUID, status: OrderStatus) -> Order:
        """Setea el estado sin validar transición. La validación la hace el use case."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        model.status = status.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def confirm_payment(
        self,
        *,
        id: UUID,
        user_id: UUID,
        culqi_charge_id: str,
        payment_method: Optional[PaymentMethod] = None,
    ) -> Order:
        """
        Marca la orden como pagada guardando el charge_id de Culqi.
        Puede aplicarse desde payment_status=pending (confirmación directa) o
        payment_status=verifying (resuelta por PayOrder o por el cronjob de reconciliación).
        El user_id se verifica para que solo el dueño de la orden pueda confirmar.
        """
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        if model.payment_status not in (PaymentStatus.pending.value, PaymentStatus.verifying.value):
            raise ValueError("payment_already_processed")
        model.payment_status = PaymentStatus.paid.value
        model.culqi_charge_id = culqi_charge_id
        if payment_method is not None:
            model.payment_method = payment_method.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def fail_payment(self, *, id: UUID, user_id: UUID) -> Order:
        """
        Marca la orden como pago fallido.
        Permite que el frontend reintente el pago con otro token/tarjeta.
        """
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        model.payment_status = PaymentStatus.failed.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def set_verifying(self, *, id: UUID, user_id: UUID) -> Order:
        """
        Marca la orden como "verifying": se intentó cobrar pero no se pudo confirmar el
        resultado a tiempo (ver PayOrder). Solo aplica desde pending, para no pisar una
        orden que ya se resolvió por otro camino mientras tanto.
        """
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        if model.payment_status != PaymentStatus.pending.value:
            raise ValueError("payment_already_processed")
        model.payment_status = PaymentStatus.verifying.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def confirm_cash_payment(self, *, id: UUID, groomer_id: UUID) -> Order:
        """
        Marca la orden como pagada en efectivo, confirmado por el groomer asignado al
        momento de la entrega. No pasa por Culqi — no hay culqi_charge_id.
        """
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        if model.groomer_id != groomer_id:
            raise ValueError("not_assigned_groomer")
        if model.payment_status not in (PaymentStatus.pending.value, PaymentStatus.verifying.value):
            raise ValueError("payment_already_processed")
        model.payment_status = PaymentStatus.paid.value
        model.payment_method = PaymentMethod.cash.value
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def list_verifying_orders(self) -> list[Order]:
        """Todas las órdenes en payment_status=verifying — usado por el cronjob de reconciliación."""
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        stmt = select(OrderModel).where(OrderModel.payment_status == PaymentStatus.verifying.value)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_order(r) for r in rows]

    async def reset_payment_to_pending(self, *, id: UUID, user_id: UUID) -> Order:
        """
        Permite reintentar el pago cuando estaba en failed.
        Solo se puede pasar de failed → pending (para un nuevo intento).
        """
        from app.modules.orders.infra.models import OrderModel, utcnow
        from app.modules.orders.domain.order import PaymentStatus
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        if model.payment_status != PaymentStatus.failed.value:
            raise ValueError("payment_not_failed")
        model.payment_status = PaymentStatus.pending.value
        model.culqi_charge_id = None
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    async def set_groomer(self, *, id: UUID, groomer_id: UUID, scheduled_at: datetime) -> Order:
        """Asigna un groomer y fecha/hora programada a la orden (lo hace el admin)."""
        from app.modules.orders.infra.models import OrderModel, utcnow
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            raise ValueError("order_not_found")
        model.groomer_id = groomer_id
        model.scheduled_at = scheduled_at
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._row_to_order(model)

    # ------------------------------------------------------------------
    # Read — usuario
    # ------------------------------------------------------------------

    async def get_order(self, *, id: UUID, user_id: UUID) -> Order:
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None or model.user_id != user_id:
            raise ValueError("order_not_found")
        return self._row_to_order(model)

    async def list_orders(self, *, user_id: UUID) -> list[Order]:
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        stmt = (
            select(OrderModel)
            .where(OrderModel.user_id == user_id)
            .order_by(desc(OrderModel.created_at))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_order(r) for r in rows]

    # ------------------------------------------------------------------
    # Read — admin
    # ------------------------------------------------------------------

    async def get_order_admin(self, *, id: UUID) -> Optional[Order]:
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        model = await self._session.get(OrderModel, id)
        if model is None:
            return None
        return self._row_to_order(model)

    async def list_orders_admin(
        self,
        *,
        status: Optional[OrderStatus] = None,
        groomer_id: Optional[UUID] = None,
    ) -> list[Order]:
        """Lista órdenes con filtros opcionales para el panel de administración."""
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        stmt = select(OrderModel).order_by(desc(OrderModel.created_at))
        if status is not None:
            stmt = stmt.where(OrderModel.status == status.value)
        if groomer_id is not None:
            stmt = stmt.where(OrderModel.groomer_id == groomer_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_order(r) for r in rows]

    # ------------------------------------------------------------------
    # Read — groomer
    # ------------------------------------------------------------------

    async def list_orders_by_groomer(
        self,
        *,
        groomer_id: UUID,
        status: Optional[OrderStatus] = None,
        scheduled_from: Optional[datetime] = None,
        scheduled_to: Optional[datetime] = None,
    ) -> list[Order]:
        """Lista las órdenes asignadas a un groomer, en orden de ruta (scheduled_at ASC).
        `scheduled_from` (inclusive) / `scheduled_to` (exclusivo) filtran por fecha programada."""
        from app.modules.orders.infra.models import OrderModel
        await self._ensure_ready()
        stmt = (
            select(OrderModel)
            .where(OrderModel.groomer_id == groomer_id)
            .order_by(OrderModel.scheduled_at.asc().nulls_last())
        )
        if status is not None:
            stmt = stmt.where(OrderModel.status == status.value)
        if scheduled_from is not None:
            stmt = stmt.where(OrderModel.scheduled_at >= scheduled_from)
        if scheduled_to is not None:
            stmt = stmt.where(OrderModel.scheduled_at < scheduled_to)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._row_to_order(r) for r in rows]

    # ------------------------------------------------------------------
    # Read — pets (recálculo de precio por peso)
    # ------------------------------------------------------------------

    async def find_recalculation_candidate(self, *, pet_id: UUID) -> Optional[Order]:
        """
        Busca una orden de esta mascota que sea candidata a recálculo de precio:
        pagada (payment_status=paid) y con el servicio aún no terminado (status != done).
        Si hay varias, devuelve la más reciente.
        """
        from app.modules.orders.infra.models import OrderModel, OrderPetModel
        await self._ensure_ready()
        stmt = (
            select(OrderModel)
            .join(OrderPetModel, OrderPetModel.order_id == OrderModel.id)
            .where(
                OrderPetModel.pet_id == pet_id,
                OrderModel.payment_status == PaymentStatus.paid.value,
                OrderModel.status != OrderStatus.done.value,
            )
            .order_by(desc(OrderModel.created_at))
        )
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        return self._row_to_order(model) if model is not None else None

    async def is_groomer_assigned_to_pet(self, *, groomer_id: UUID, pet_id: UUID) -> bool:
        """
        Verifica si el groomer está asignado a alguna orden activa (no done/cancelled) que
        incluya a esta mascota — usado para autorizar POST /pets/{pet_id}/records cuando
        quien llama no es el dueño ni un admin.
        """
        from app.modules.orders.infra.models import OrderModel, OrderPetModel
        await self._ensure_ready()
        stmt = (
            select(OrderModel.id)
            .join(OrderPetModel, OrderPetModel.order_id == OrderModel.id)
            .where(
                OrderPetModel.pet_id == pet_id,
                OrderModel.groomer_id == groomer_id,
                OrderModel.status.notin_([OrderStatus.done.value, OrderStatus.cancelled.value]),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None
