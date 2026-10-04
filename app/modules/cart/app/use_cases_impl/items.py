from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItem, CartItemKind, CartRepository, CartSession, CartStatus

from .common import _raise_cart_error
from .hold_binding import CartHolds, base_line, line_hold_id
from .pricing import CartPricing
from .validation import (
    _validate_required_meta_fields,
    _validate_single_base_service,
)


def _item_to_line(item: CartItem) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "ref_id": item.ref_id,
        "name": item.name,
        "qty": item.qty,
        "unit_price": item.unit_price,
        "meta": item.meta,
    }


def _new_items(cart_id: UUID, lines: list[dict[str, Any]]) -> list[CartItem]:
    return [
        CartItem.new(
            cart_id=cart_id,
            kind=line["kind"],
            ref_id=line["ref_id"],
            name=line.get("name"),
            qty=line.get("qty", 1),
            unit_price=line.get("unit_price"),
            meta=line.get("meta"),
        )
        for line in lines
    ]


async def _bind(holds: Optional[CartHolds], lines: list[dict[str, Any]], *, user_id: UUID) -> list[dict[str, Any]]:
    return await holds.bind(lines, user_id=user_id) if holds is not None else lines


@dataclass
class CreateCartWithItems:
    repo: CartRepository
    pricing: CartPricing
    holds: Optional[CartHolds] = None

    async def execute(
        self,
        *,
        user_id: UUID,
        items: list[dict[str, Any]],
    ) -> tuple[CartSession, list[CartItem]]:
        _validate_single_base_service(items)
        _validate_required_meta_fields(items)
        bound = await _bind(self.holds, items, user_id=user_id)
        priced = await self.pricing.price_lines(bound, user_id=user_id)

        cart = await self.repo.create_cart(user_id=user_id)

        try:
            added_items = await self.repo.add_items(cart_id=cart.id, user_id=user_id, items=_new_items(cart.id, priced))
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise
        if self.holds is not None:
            await self.holds.attach(line_hold_id(base_line(priced)), cart_expires_at=cart.expires_at)
        return cart, added_items


@dataclass
class AddItem:
    repo: CartRepository
    pricing: CartPricing
    holds: Optional[CartHolds] = None

    async def execute(
        self,
        *,
        cart_id: UUID,
        user_id: UUID,
        kind: CartItemKind,
        ref_id: Union[UUID, str],
        name: Optional[str] = None,
        qty: int = 1,
        unit_price: Optional[float] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> CartItem:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        new_line = {"kind": kind, "ref_id": ref_id, "name": name, "qty": qty, "unit_price": unit_price, "meta": meta}
        is_base = CartItemKind(getattr(kind, "value", kind)) == CartItemKind.service_base
        if is_base:
            _validate_required_meta_fields([new_line])

        # Se cotiza el carrito completo (lo que ya tiene + el ítem nuevo): un addon necesita el
        # servicio base y la mascota de ese servicio para tener precio.
        existing = await self.repo.list_items(cart_id=cart_id, user_id=user_id)
        lines = await _bind(self.holds, [_item_to_line(i) for i in existing] + [new_line], user_id=user_id)
        priced = await self.pricing.price_lines(lines, user_id=user_id)

        item = _new_items(cart_id, [priced[-1]])[0]
        try:
            added = await self.repo.add_item(cart_id=cart_id, user_id=user_id, item=item)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise
        if self.holds is not None and is_base:
            await self.holds.attach(line_hold_id(priced[-1]), cart_expires_at=cart.expires_at)
        return added


@dataclass
class RemoveItem:
    repo: CartRepository
    holds: Optional[CartHolds] = None

    async def execute(self, *, cart_id: UUID, user_id: UUID, item_id: UUID) -> None:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        # Si se quita el servicio base, su reserva de cupo se libera.
        released_hold = None
        if self.holds is not None:
            items = await self.repo.list_items(cart_id=cart_id, user_id=user_id)
            removed = next((i for i in items if i.id == item_id), None)
            if removed is not None and CartItemKind(getattr(removed.kind, "value", removed.kind)) == CartItemKind.service_base:
                released_hold = line_hold_id(_item_to_line(removed))

        try:
            await self.repo.remove_item(cart_id=cart_id, user_id=user_id, item_id=item_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise
        if self.holds is not None:
            await self.holds.release(released_hold)


@dataclass
class ListItems:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> list[CartItem]:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        return await self.repo.list_items(cart_id=cart_id, user_id=user_id)


@dataclass
class AddItemsBatch:
    repo: CartRepository
    pricing: CartPricing
    holds: Optional[CartHolds] = None

    async def execute(
        self,
        *,
        cart_id: UUID,
        user_id: UUID,
        items: list[dict[str, Any]],
    ) -> list[CartItem]:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        _validate_single_base_service(items)
        _validate_required_meta_fields(items)

        existing = await self.repo.list_items(cart_id=cart_id, user_id=user_id)
        lines = await _bind(self.holds, [_item_to_line(i) for i in existing] + list(items), user_id=user_id)
        priced = await self.pricing.price_lines(lines, user_id=user_id)

        try:
            added = await self.repo.add_items(
                cart_id=cart_id, user_id=user_id, items=_new_items(cart_id, priced[len(existing):]),
            )
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise
        if self.holds is not None:
            await self.holds.attach(line_hold_id(base_line(priced)), cart_expires_at=cart.expires_at)
        return added


@dataclass
class ReplaceAllItems:
    repo: CartRepository
    pricing: CartPricing
    holds: Optional[CartHolds] = None

    async def execute(
        self,
        *,
        cart_id: UUID,
        user_id: UUID,
        items: list[dict[str, Any]],
    ) -> list[CartItem]:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        _validate_single_base_service(items)
        _validate_required_meta_fields(items)
        bound = await _bind(self.holds, items, user_id=user_id)
        priced = await self.pricing.price_lines(bound, user_id=user_id)

        previous_hold = None
        if self.holds is not None:
            previous = await self.repo.list_items(cart_id=cart_id, user_id=user_id)
            previous_hold = line_hold_id(base_line([_item_to_line(i) for i in previous]))

        try:
            replaced = await self.repo.replace_all_items(
                cart_id=cart_id, user_id=user_id, items=_new_items(cart_id, priced),
            )
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if self.holds is not None:
            new_hold = line_hold_id(base_line(priced))
            await self.holds.attach(new_hold, cart_expires_at=cart.expires_at)
            if previous_hold is not None and previous_hold != new_hold:
                # Cambió de servicio/fecha: la reserva anterior ya no se usa.
                await self.holds.release(previous_hold)
        return replaced
