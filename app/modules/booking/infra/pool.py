"""Cupo diario compartido por categoría (feature 0007).

El negocio abre N cupos por día para toda la categoría (p. ej. 10 para PAKU Spa), no N por servicio.
Sin cambiar el esquema: todos los servicios de una categoría usan el cupo (`availability_slots`) del
servicio más antiguo de esa categoría, el "ancla". Cualquier reserva de cualquier servicio descuenta
de ese único cupo.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def pool_service_id(session: AsyncSession, service_id: UUID) -> UUID:
    """Servicio ancla cuyo cupo comparte `service_id` (él mismo si no tiene categoría)."""
    from app.modules.store.infra.db_models import ProductModel

    category_id = (
        await session.execute(select(ProductModel.category_id).where(ProductModel.id == service_id))
    ).scalar()
    if category_id is None:
        return service_id
    anchor = (
        await session.execute(
            select(ProductModel.id)
            .where(ProductModel.category_id == category_id)
            .order_by(ProductModel.created_at.asc(), ProductModel.id.asc())
            .limit(1)
        )
    ).scalar()
    return anchor or service_id


async def pool_member_ids(session: AsyncSession, service_id: UUID) -> list[UUID]:
    """Todos los servicios que comparten el cupo de `service_id`."""
    from app.modules.store.infra.db_models import ProductModel

    category_id = (
        await session.execute(select(ProductModel.category_id).where(ProductModel.id == service_id))
    ).scalar()
    if category_id is None:
        return [service_id]
    rows = await session.execute(select(ProductModel.id).where(ProductModel.category_id == category_id))
    return list(rows.scalars().all())


async def anchor_ids(session: AsyncSession) -> set[UUID]:
    """Anclas de todas las categorías (los únicos cupos que se usan)."""
    from app.modules.store.infra.db_models import ProductModel

    rows = (
        await session.execute(
            select(ProductModel.id, ProductModel.category_id).order_by(
                ProductModel.category_id, ProductModel.created_at.asc(), ProductModel.id.asc()
            )
        )
    ).all()
    seen: dict = {}
    for pid, cid in rows:
        seen.setdefault(cid, pid)
    return set(seen.values())


async def pool_labels(session: AsyncSession, service_ids: list[UUID]) -> dict[UUID, str]:
    """Nombre a mostrar del cupo: "<categoría> · todos los servicios"."""
    from app.modules.store.infra.db_models import CategoryModel, ProductModel

    if not service_ids:
        return {}
    rows = await session.execute(
        select(ProductModel.id, CategoryModel.name)
        .join(CategoryModel, CategoryModel.id == ProductModel.category_id)
        .where(ProductModel.id.in_(service_ids))
    )
    return {pid: f"{name} · todos los servicios" for pid, name in rows.all()}


async def default_pool_service_id(session: AsyncSession) -> Optional[UUID]:
    """Cupo "del día" cuando el admin no indica servicio (feature 0007): el de la primera categoría
    activa que tiene servicios (hoy, PAKU Spa)."""
    from app.modules.store.infra.db_models import CategoryModel, ProductModel

    first = (
        await session.execute(
            select(ProductModel.id)
            .join(CategoryModel, CategoryModel.id == ProductModel.category_id)
            .where(CategoryModel.is_active.is_(True))
            .order_by(CategoryModel.created_at.asc(), CategoryModel.id.asc())
            .limit(1)
        )
    ).scalar()
    return await pool_service_id(session, first) if first else None
