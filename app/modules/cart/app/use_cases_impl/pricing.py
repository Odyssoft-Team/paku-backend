"""
Precios del carrito calculados por el backend.

El front puede seguir enviando `unit_price` y `name` en los ítems, pero se ignoran: el precio y el
nombre salen de `store` con la misma lógica que `POST /store/quote` (`price_service`), según la
especie, la raza y el peso de la mascota del servicio base.

Formato único de ítems:
- `service_base`: `ref_id` = id del servicio (store product), `meta.pet_id` obligatorio.
- `service_addon`: `ref_id` = id del addon; se liga al único servicio base del carrito. No necesita
  meta (`requires_base`, `base_service_id`, `addon_ids` se aceptan y se ignoran). El backend le
  completa `meta.pet_id` (lo usa el ajuste de precio por peso).
- `product` (producto físico): no soportado; `store` no tiene precios para productos físicos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItemKind

from .common import _kind_value, _meta_dict

# Diferencia mínima (en soles) para considerar que un precio cambió.
PRICE_TOLERANCE = 0.005


def _error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})


def _as_uuid(value: Any, *, code: str, message: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise _error(status.HTTP_400_BAD_REQUEST, code, message, value=str(value))


def prices_differ(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is not b
    return abs(float(a) - float(b)) > PRICE_TOLERANCE


@dataclass
class CartPricing:
    """Cotiza las líneas de un carrito. `store_repo`: PostgresStoreRepository; `pets_repo`: PetRepository."""
    store_repo: Any
    pets_repo: Any

    async def price_lines(self, lines: list[dict[str, Any]], *, user_id: UUID) -> list[dict[str, Any]]:
        """
        Recibe todas las líneas que quedarán en el carrito (dicts con kind, ref_id, name, qty,
        unit_price, meta) y devuelve copias en el mismo orden con `unit_price` y `name` del servidor.
        """
        from app.modules.store.app.use_cases_impl.quote import price_service

        for line in lines:
            if _kind_value(line.get("kind")) == CartItemKind.product.value:
                raise _error(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "PRODUCT_NOT_SUPPORTED",
                    "Los productos físicos no se venden por el carrito todavía.",
                    ref_id=str(line.get("ref_id")),
                )

        bases = [l for l in lines if _kind_value(l.get("kind")) == CartItemKind.service_base.value]
        addons = [l for l in lines if _kind_value(l.get("kind")) == CartItemKind.service_addon.value]

        if not bases:
            if addons:
                raise _error(
                    status.HTTP_400_BAD_REQUEST,
                    "BASE_SERVICE_REQUIRED",
                    "Un complemento solo se puede agregar junto a un servicio de baño/grooming.",
                )
            return [dict(l) for l in lines]
        if len(bases) > 1:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                "MULTIPLE_BASE_SERVICES",
                "Solo se permite un servicio base por carrito.",
            )

        base = bases[0]
        pet_id = _as_uuid(
            _meta_dict(base.get("meta")).get("pet_id"),
            code="PET_REQUIRED",
            message="El servicio base necesita meta.pet_id.",
        )
        pet = await self.pets_repo.get_by_id(pet_id)
        if pet is None:
            raise _error(status.HTTP_404_NOT_FOUND, "PET_NOT_FOUND", "Mascota no encontrada.", pet_id=str(pet_id))
        if pet.owner_id != user_id:
            raise _error(status.HTTP_403_FORBIDDEN, "PET_NOT_OWNED", "La mascota no pertenece al usuario.")

        product_id = _as_uuid(base.get("ref_id"), code="INVALID_SERVICE_ID", message="ref_id del servicio inválido.")
        addon_ids = [
            _as_uuid(a.get("ref_id"), code="INVALID_ADDON_ID", message="ref_id del complemento inválido.")
            for a in addons
        ]
        if len(set(addon_ids)) != len(addon_ids):
            raise _error(status.HTTP_400_BAD_REQUEST, "DUPLICATE_ADDON", "Un complemento está repetido en el carrito.")

        quote = await price_service(self.store_repo, pet=pet, product_id=product_id, addon_ids=addon_ids)
        priced = {quote.product.target_id: quote.product}
        priced.update({a.target_id: a for a in quote.addons})

        out: list[dict[str, Any]] = []
        for line in lines:
            new = dict(line)
            quote_line = priced[UUID(str(line.get("ref_id")))]
            new["unit_price"] = float(quote_line.price)
            new["name"] = quote_line.name
            if _kind_value(line.get("kind")) == CartItemKind.service_addon.value:
                meta = dict(_meta_dict(line.get("meta")))
                meta["pet_id"] = str(pet_id)
                new["meta"] = meta
            out.append(new)
        return out
