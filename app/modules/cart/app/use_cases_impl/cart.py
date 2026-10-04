from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItemKind, CartRepository, CartSession, CartStatus

from .common import _is_kind, _meta_dict, _raise_cart_error
from .hold_binding import CartHolds
from .pricing import CartPricing, prices_differ


@dataclass
class CreateCart:
    repo: CartRepository

    async def execute(self, *, user_id: UUID) -> CartSession:
        return await self.repo.create_cart(user_id=user_id)


@dataclass
class GetCart:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> CartSession:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")
        return cart


@dataclass
class GetOrCreateActiveCart:
    repo: CartRepository

    async def execute(self, *, user_id: UUID) -> CartSession:
        cart = await self.repo.get_active_cart_for_user(user_id=user_id)

        if cart is None:
            cart = await self.repo.create_cart(user_id=user_id)

        return cart


@dataclass
class Checkout:
    repo: CartRepository
    pricing: CartPricing
    holds: Optional[CartHolds] = None

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> CartSession:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        if self.holds is not None:
            # La reserva del día debe seguir vigente; si venció → 409 HOLD_EXPIRED (elegir fecha de nuevo).
            items = await self.repo.list_items(cart_id=cart_id, user_id=user_id)
            await self.holds.assert_still_valid(
                [{"kind": i.kind, "ref_id": i.ref_id, "meta": i.meta} for i in items], user_id=user_id,
            )

        await self._reprice_or_fail(cart_id=cart_id, user_id=user_id)

        try:
            return await self.repo.checkout(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

    async def _reprice_or_fail(self, *, cart_id: UUID, user_id: UUID) -> None:
        """
        El carrito vive 2 horas: entre "agregar" y "checkout" pudo cambiar una regla de precio o el
        peso de la mascota. Se recotiza; si algo cambió, se guardan los precios nuevos y se responde
        409 PRICE_CHANGED con el detalle para que el cliente vea y confirme el monto nuevo.
        Nunca se cierra un carrito con un monto que el cliente no vio.
        """
        items = await self.repo.list_items(cart_id=cart_id, user_id=user_id)
        lines = [
            {"kind": i.kind, "ref_id": i.ref_id, "name": i.name, "qty": i.qty,
             "unit_price": i.unit_price, "meta": i.meta}
            for i in items
        ]
        priced = await self.pricing.price_lines(lines, user_id=user_id)

        price_changes = [
            {
                "item_id": str(item.id),
                "name": line["name"],
                "old_unit_price": item.unit_price,
                "new_unit_price": line["unit_price"],
            }
            for item, line in zip(items, priced)
            if prices_differ(item.unit_price, line["unit_price"])
        ]
        stale = any(
            prices_differ(item.unit_price, line["unit_price"])
            or item.name != line["name"]
            or (item.meta or None) != (line.get("meta") or None)
            for item, line in zip(items, priced)
        )
        if stale:
            await self.repo.update_item_prices(
                cart_id=cart_id,
                prices={
                    item.id: (line["unit_price"], line["name"], line.get("meta"))
                    for item, line in zip(items, priced)
                },
            )
        if not price_changes:
            return  # solo cambió el nombre/meta: se corrige sin molestar al cliente

        new_total = round(sum(float(l["unit_price"]) * int(l.get("qty") or 1) for l in priced), 2)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PRICE_CHANGED",
                "message": "Los precios del carrito cambiaron. Revisa el nuevo total y confirma de nuevo.",
                "items": price_changes,
                "total": new_total,
                "currency": "PEN",
            },
        )


@dataclass
class ValidateCart:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            return {
                "valid": False,
                "errors": [f"Cart error: {str(exc)}"],
                "warnings": [],
                "total": 0.0,
            }

        if cart.status == CartStatus.expired:
            return {
                "valid": False,
                "errors": ["Cart has expired"],
                "warnings": [],
                "total": 0.0,
            }

        items = await self.repo.list_items(cart_id=cart_id, user_id=user_id)

        if not items:
            return {
                "valid": False,
                "errors": ["Cart is empty. Add at least one service."],
                "warnings": [],
                "total": 0.0,
            }

        base_services = [
            i for i in items if _is_kind(getattr(i, "kind", None), CartItemKind.service_base)
        ]

        if not base_services:
            errors.append("Cart must have at least one base service")
        elif len(base_services) > 1:
            errors.append(f"Cart has {len(base_services)} base services, only 1 allowed")

        total = 0.0
        for item in items:
            if item.unit_price is None or item.unit_price <= 0:
                errors.append(f"Item '{item.name or item.ref_id}' has invalid price")
            else:
                total += float(item.unit_price) * int(item.qty)

        for item in items:
            if _is_kind(getattr(item, "kind", None), CartItemKind.service_base):
                meta = _meta_dict(getattr(item, "meta", None))

                if not meta.get("pet_id"):
                    errors.append(f"Service '{item.name}' missing required field: pet_id")

                if not meta.get("scheduled_date"):
                    errors.append(f"Service '{item.name}' missing required field: scheduled_date")

                if not meta.get("scheduled_time"):
                    errors.append(f"Service '{item.name}' missing required field: scheduled_time")

        # Que cada addon pertenezca al servicio base lo valida la cotización (store) al agregar
        # y en el checkout; meta.requires_base / base_service_id ya no se usan.

        if total == 0:
            warnings.append("Total is 0. Please verify prices.")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total": total,
        }
