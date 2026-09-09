"""
Órdenes de ajuste — cobro adicional cuando el peso real de la mascota (confirmado por
admin/ally) da un precio mayor al ya cobrado en la orden original. Ver plan de rediseño:
requiere confirmación explícita (no se crea solo por detectar la diferencia).
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.orders.domain.order import Order
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.orders.app.use_cases_impl.price_recalc import compute_price_check
from app.modules.pets.domain.pet import PetRepository
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository
from app.modules.store.domain.models import Species
from app.modules.store.app.use_cases_impl.quote import _breed_category


@dataclass
class CreateAdjustmentOrder:
    orders_repo: PostgresOrderRepository
    pets_repo: PetRepository
    store_repo: PostgresStoreRepository

    async def execute(self, *, order_id: UUID, pet_id: UUID) -> Order:
        order = await self.orders_repo.get_order_admin(id=order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        pet = await self.pets_repo.get_by_id(pet_id)
        if pet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        # El precio se recalcula aquí de nuevo (server-side, con el peso actual de la
        # mascota) en vez de confiar en un monto que mande el front — evita manipulación.
        species = Species(str(pet.species.value if hasattr(pet.species, "value") else pet.species))
        breed_category = _breed_category(pet.breed_id, pet.breed_name)
        price_check = await compute_price_check(
            store_repo=self.store_repo,
            order=order,
            pet_id=pet_id,
            species=species,
            breed_category=breed_category,
            new_weight=float(pet.weight_kg) if pet.weight_kg else 0.0,
        )
        if price_check is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No hay diferencia de precio que cobrar para esta orden/mascota",
            )
        if price_check["difference"] <= 0:
            # Precio menor (cliente pagó de más): fuera de alcance, requiere reembolsos.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El nuevo precio es menor al ya cobrado — los reembolsos no están soportados todavía",
            )

        adjustment = Order.new(
            user_id=order.user_id,
            items_snapshot=[{
                "kind": "price_adjustment",
                "ref_id": str(order.id),
                "name": "Ajuste por diferencia de peso",
                "qty": 1,
                "unit_price": price_check["difference"],
                "meta": {"pet_id": str(pet_id), "reason": "weight_recalculation"},
            }],
            total_snapshot=price_check["difference"],
            currency=order.currency,
            delivery_address_snapshot=order.delivery_address_snapshot,
            parent_order_id=order.id,
        )
        created = await self.orders_repo.create_order(adjustment)
        await self.orders_repo.add_order_pets(order_id=created.id, pet_ids=[pet_id])

        try:
            from app.core.db import engine
            from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
            from app.modules.notifications.app.use_cases import CreateNotification

            notifications_repo = PostgresNotificationRepository(session=self.orders_repo._session, engine=engine)
            await CreateNotification(repo=notifications_repo).execute(
                user_id=order.user_id,
                type="order_status",
                title="Cargo adicional generado",
                body=(
                    f"Tu mascota pesa más de lo declarado — se generó un cargo adicional de "
                    f"{order.currency} {price_check['difference']:.2f}."
                ),
                data={"order_id": str(created.id), "parent_order_id": str(order.id)},
            )
        except Exception:
            import logging
            logging.exception("Failed to notify adjustment order %s", created.id)

        return created
