from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItem, CartItemKind, CartRepository, CartSession, CartStatus

from .common import _raise_cart_error
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


@dataclass
class CreateCartWithItems:
    repo: CartRepository
    pricing: CartPricing

    async def execute(
        self,
        *,
        user_id: UUID,
        items: list[dict[str, Any]],
    ) -> tuple[CartSession, list[CartItem]]:
        _validate_single_base_service(items)
        _validate_required_meta_fields(items)
        priced = await self.pricing.price_lines(items, user_id=user_id)

        cart = await self.repo.create_cart(user_id=user_id)

        try:
            added_items = await self.repo.add_items(cart_id=cart.id, user_id=user_id, items=_new_items(cart.id, priced))
            return cart, added_items
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class AddItem:
    repo: CartRepository
    pricing: CartPricing

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
        if CartItemKind(getattr(kind, "value", kind)) == CartItemKind.service_base:
            _validate_required_meta_fields([new_line])

        # Se cotiza el carrito completo (lo que ya tiene + el ítem nuevo): un addon necesita el
        # servicio base y la mascota de ese servicio para tener precio.
        existing = await self.repo.list_items(cart_id=cart_id, user_id=user_id)
        priced = await self.pricing.price_lines(
            [_item_to_line(i) for i in existing] + [new_line], user_id=user_id,
        )

        item = _new_items(cart_id, [priced[-1]])[0]
        try:
            return await self.repo.add_item(cart_id=cart_id, user_id=user_id, item=item)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class RemoveItem:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID, item_id: UUID) -> None:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        try:
            await self.repo.remove_item(cart_id=cart_id, user_id=user_id, item_id=item_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


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
        priced = await self.pricing.price_lines(
            [_item_to_line(i) for i in existing] + list(items), user_id=user_id,
        )

        try:
            return await self.repo.add_items(
                cart_id=cart_id, user_id=user_id, items=_new_items(cart_id, priced[len(existing):]),
            )
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class ReplaceAllItems:
    repo: CartRepository
    pricing: CartPricing

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
        priced = await self.pricing.price_lines(items, user_id=user_id)

        try:
            return await self.repo.replace_all_items(
                cart_id=cart_id, user_id=user_id, items=_new_items(cart_id, priced),
            )
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise
