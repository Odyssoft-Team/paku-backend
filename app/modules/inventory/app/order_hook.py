"""Consumo automático de insumos al terminar una orden (feature 0009).

Lo llaman los dos caminos a `done`: `CompleteOrder` (groomer) y el cambio de estado del admin
("cerrar a mano"). Best effort: la orden ya quedó terminada; si el consumo falla se deja en el log y el
admin lo registra después con `POST /admin/inventory/orders/{id}/consume`.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def register_order_consumption(session: AsyncSession, order) -> None:
    from app.core.db import engine
    from app.modules.inventory.app.use_cases import OrderConsumption
    from app.modules.inventory.infra.postgres_inventory_repository import PostgresInventoryRepository
    from app.modules.orders.domain.order import OrderStatus
    from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
    from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

    if order.status != OrderStatus.done or order.parent_order_id is not None:
        return
    try:
        await OrderConsumption(
            repo=PostgresInventoryRepository(session=session),
            store_repo=PostgresStoreRepository(session=session, engine=engine),
            pets_repo=PostgresPetRepository(session=session, engine=engine),
        ).register(order)
    except HTTPException as exc:
        logger.info("Consumo de insumos no registrado para la orden %s: %s", order.id, exc.detail)
    except Exception as exc:
        logger.exception("Falló el consumo de insumos de la orden %s: %s", order.id, exc)
        try:
            await session.rollback()  # deja la sesión usable para la notificación que sigue
        except Exception:
            pass
