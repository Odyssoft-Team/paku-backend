from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItem, CartItemKind, CartRepository, CartSession, CartStatus

from .common import _raise_cart_error
from .validation import (
    _validate_addon_dependencies,
    _validate_required_meta_fields,
    _validate_single_base_service,
)


@dataclass
class CreateCartWithItems:
    repo: CartRepository

    async def execute(
        self,
        *,
        user_id: UUID,
        items: list[dict[str, Any]],
    ) -> tuple[CartSession, list[CartItem]]:
        _validate_single_base_service(items)
        _validate_required_meta_fields(items)
        _validate_addon_dependencies(items)

        cart = await self.repo.create_cart(user_id=user_id)

        cart_items = [
            CartItem.new(
                cart_id=cart.id,
                kind=item["kind"],
                ref_id=item["ref_id"],
                name=item.get("name"),
                qty=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                meta=item.get("meta"),
            )
            for item in items
        ]

        try:
            added_items = await self.repo.add_items(cart_id=cart.id, user_id=user_id, items=cart_items)
            return cart, added_items
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class AddItem:
    repo: CartRepository

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

        item = CartItem.new(
            cart_id=cart_id,
            kind=kind,
            ref_id=ref_id,
            name=name,
            qty=qty,
            unit_price=unit_price,
            meta=meta,
        )
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
        _validate_addon_dependencies(items)

        cart_items = [
            CartItem.new(
                cart_id=cart_id,
                kind=item["kind"],
                ref_id=item["ref_id"],
                name=item.get("name"),
                qty=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                meta=item.get("meta"),
            )
            for item in items
        ]

        try:
            return await self.repo.add_items(cart_id=cart_id, user_id=user_id, items=cart_items)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class ReplaceAllItems:
    repo: CartRepository

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
        _validate_addon_dependencies(items)

        cart_items = [
            CartItem.new(
                cart_id=cart_id,
                kind=item["kind"],
                ref_id=item["ref_id"],
                name=item.get("name"),
                qty=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                meta=item.get("meta"),
            )
            for item in items
        ]

        try:
            return await self.repo.replace_all_items(cart_id=cart_id, user_id=user_id, items=cart_items)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise
