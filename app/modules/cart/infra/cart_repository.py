from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
from uuid import UUID

from app.modules.cart.domain.cart import CartItem, CartRepository, CartSession, CartStatus


class InMemoryCartRepository(CartRepository):
    def __init__(self) -> None:
        self._carts: Dict[UUID, CartSession] = {}
        self._items_by_cart: Dict[UUID, List[CartItem]] = {}

    def _assert_owner(self, cart: CartSession, user_id: UUID) -> None:
        if cart.user_id != user_id:
            raise ValueError("cart_not_found")

    def _apply_expiration(self, cart: CartSession) -> CartSession:
        if cart.status == CartStatus.expired:
            return cart

        now = datetime.now(timezone.utc)
        if now > cart.expires_at and cart.status == CartStatus.active:
            expired = CartSession(
                id=cart.id,
                user_id=cart.user_id,
                status=CartStatus.expired,
                expires_at=cart.expires_at,
                created_at=cart.created_at,
                updated_at=now,
            )
            self._carts[cart.id] = expired
            return expired
        return cart

    def create_cart(self, user_id: UUID) -> CartSession:
        cart = CartSession.new(user_id=user_id)
        self._carts[cart.id] = cart
        self._items_by_cart[cart.id] = []
        return cart

    def get_cart(self, cart_id: UUID, user_id: UUID) -> CartSession:
        cart = self._carts.get(cart_id)
        if not cart:
            raise ValueError("cart_not_found")
        self._assert_owner(cart, user_id)
        return self._apply_expiration(cart)

    def add_item(self, cart_id: UUID, user_id: UUID, item: CartItem) -> CartItem:
        cart = self.get_cart(cart_id, user_id)
        if cart.status != CartStatus.active:
            raise ValueError("cart_not_active")

        if item.cart_id != cart_id:
            raise ValueError("invalid_cart_item")

        self._items_by_cart.setdefault(cart_id, []).append(item)
        updated_cart = CartSession(
            id=cart.id,
            user_id=cart.user_id,
            status=cart.status,
            expires_at=cart.expires_at,
            created_at=cart.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._carts[cart_id] = updated_cart
        return item

    def remove_item(self, cart_id: UUID, user_id: UUID, item_id: UUID) -> None:
        cart = self.get_cart(cart_id, user_id)
        if cart.status != CartStatus.active:
            raise ValueError("cart_not_active")

        items = self._items_by_cart.get(cart_id, [])
        before = len(items)
        self._items_by_cart[cart_id] = [i for i in items if i.id != item_id]
        if len(self._items_by_cart[cart_id]) == before:
            raise ValueError("item_not_found")

        updated_cart = CartSession(
            id=cart.id,
            user_id=cart.user_id,
            status=cart.status,
            expires_at=cart.expires_at,
            created_at=cart.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._carts[cart_id] = updated_cart

    def list_items(self, cart_id: UUID, user_id: UUID) -> list[CartItem]:
        _ = self.get_cart(cart_id, user_id)
        return list(self._items_by_cart.get(cart_id, []))

    def checkout(self, cart_id: UUID, user_id: UUID) -> CartSession:
        cart = self.get_cart(cart_id, user_id)
        if cart.status != CartStatus.active:
            raise ValueError("cart_not_active")

        updated = CartSession(
            id=cart.id,
            user_id=cart.user_id,
            status=CartStatus.checked_out,
            expires_at=cart.expires_at,
            created_at=cart.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._carts[cart_id] = updated
        return updated
