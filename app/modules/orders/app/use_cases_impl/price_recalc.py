"""
Recálculo de precio por peso — compartido entre pet_records (detección al registrar
weight_record) y orders (creación de la orden de ajuste tras confirmación explícita).
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from app.modules.orders.domain.order import Order
from app.modules.store.domain.models import Species
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

_KIND_TO_TARGET_TYPE = {"service_base": "product", "service_addon": "addon"}


def items_for_pet(items_snapshot: list[dict], pet_id: UUID) -> list[dict]:
    """Filtra los items de una orden que pertenecen a una mascota específica (una orden
    puede cubrir servicios de más de una mascota, cada item trae su propio meta.pet_id)."""
    result = []
    for item in items_snapshot or []:
        meta = item.get("meta") or {}
        if str(meta.get("pet_id")) == str(pet_id):
            result.append(item)
    return result


async def compute_price_check(
    *,
    store_repo: PostgresStoreRepository,
    order: Order,
    pet_id: UUID,
    species: Species,
    breed_category: str,
    new_weight: float,
) -> Optional[dict[str, Any]]:
    """
    Recalcula el precio de los items de esta mascota dentro de la orden usando el peso
    nuevo, y lo compara contra lo ya cobrado. Devuelve None si no hay diferencia relevante
    (o no hay items de servicio para esta mascota).
    """
    items = items_for_pet(order.items_snapshot, pet_id)
    if not items:
        return None

    old_total = 0.0
    new_total = 0.0
    for item in items:
        target_type = _KIND_TO_TARGET_TYPE.get(item.get("kind"))
        if target_type is None:
            continue  # producto físico, no tiene precio por peso
        qty = int(item.get("qty", 1))
        unit_price = item.get("unit_price")
        if unit_price is not None:
            old_total += float(unit_price) * qty
        try:
            ref_id = UUID(str(item["ref_id"]))
        except (KeyError, ValueError):
            continue
        new_unit_price = await store_repo.price_for(
            target_id=ref_id,
            target_type=target_type,
            species=species,
            breed_category=breed_category,
            weight=new_weight,
        )
        if new_unit_price is not None:
            new_total += new_unit_price * qty
        elif unit_price is not None:
            new_total += float(unit_price) * qty  # sin regla nueva: asume mismo precio

    difference = round(new_total - old_total, 2)
    if abs(difference) < 0.01:
        return None
    return {
        "order_id": str(order.id),
        "old_price": round(old_total, 2),
        "new_price": round(new_total, 2),
        "difference": difference,
    }
