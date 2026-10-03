"""
Vista de una parada para la app Paku Groomer (pedido 2 del front): la orden más los datos de la
mascota, del cliente y del servicio. No agrega campos en BD: son lecturas sobre lo que ya existe.
"""
from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID

from app.modules.orders.domain.order import Order


def _kind(item: dict) -> Optional[str]:
    return item.get("kind")


def base_item(order: Order) -> Optional[dict]:
    for item in order.items_snapshot or []:
        if _kind(item) == "service_base":
            return item
    return None


def order_pet_id(order: Order) -> Optional[UUID]:
    """1 orden = 1 mascota: la del servicio base (meta.pet_id)."""
    base = base_item(order)
    raw = ((base or {}).get("meta") or {}).get("pet_id")
    try:
        return UUID(str(raw)) if raw else None
    except ValueError:
        return None


def purchased_addons(order: Order) -> list[dict[str, Any]]:
    """
    Addons comprados en la orden: líneas `service_addon` (formato actual) y, para órdenes antiguas,
    `meta.addon_ids` del servicio base. Devuelve [{"id", "name"}] sin repetidos; `name` puede ser None
    si la orden antigua no lo guardó.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in order.items_snapshot or []:
        if _kind(item) == "service_addon" and item.get("ref_id"):
            addon_id = str(item["ref_id"])
            if addon_id not in seen:
                seen.add(addon_id)
                out.append({"id": addon_id, "name": item.get("name")})
    base = base_item(order)
    for raw in ((base or {}).get("meta") or {}).get("addon_ids") or []:
        addon_id = str(raw)
        if addon_id not in seen:
            seen.add(addon_id)
            out.append({"id": addon_id, "name": None})
    return out


async def build_groomer_view(
    order: Order,
    *,
    pets_repo,
    users_repo,
    store_repo,
    signed_url: Callable[[Optional[str]], Optional[str]],
) -> dict[str, Any]:
    """Devuelve {"pet", "client", "service"} para la orden (cada uno puede ser None)."""
    pet_out = None
    pet_id = order_pet_id(order)
    if pet_id is not None:
        pet = await pets_repo.get_by_id(pet_id, include_deleted=True)
        if pet is not None:
            pet_out = {
                "id": pet.id,
                "name": pet.name,
                "species": getattr(pet.species, "value", pet.species),
                "breed_name": pet.breed_name,
                "sex": getattr(pet.sex, "value", pet.sex),
                "birth_date": pet.birth_date,
                "weight_kg": pet.weight_kg,
                "photo_url": signed_url(pet.photo_url),
                "notes": pet.notes,
                "skin_sensitivity": pet.skin_sensitivity,
                "bath_behavior": getattr(pet.bath_behavior, "value", pet.bath_behavior),
                "tolerates_drying": pet.tolerates_drying,
                "tolerates_nail_clipping": pet.tolerates_nail_clipping,
                "special_shampoo": pet.special_shampoo,
            }

    client_out = None
    user = await users_repo.get_by_id(order.user_id)
    if user is not None:
        client_out = {"first_name": user.first_name, "last_name": user.last_name, "phone": user.phone}

    service_out = None
    base = base_item(order)
    if base is not None:
        addons = purchased_addons(order)
        for addon in addons:
            if addon["name"] is None:
                try:
                    found = await store_repo.get_addon(UUID(addon["id"]))
                except ValueError:
                    found = None
                addon["name"] = found.name if found else None
        service_out = {"name": base.get("name"), "addons": addons}

    return {"pet": pet_out, "client": client_out, "service": service_out}
