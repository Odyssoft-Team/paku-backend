from dataclasses import dataclass
from typing import Any, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItem, CartItemKind, CartRepository, CartSession, CartStatus


def _raise_cart_error(code: str) -> None:
    if code == "cart_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    if code == "cart_not_active":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart is not active (expired/checked out/cancelled)")
    if code == "item_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if code == "invalid_cart_item":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cart item")


@dataclass
class CreateCart:
    repo: CartRepository

    async def execute(self, *, user_id: UUID) -> CartSession:
        return self.repo.create_cart(user_id=user_id)


@dataclass
class GetCart:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> CartSession:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
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
        """
        Obtiene el carrito activo del usuario, o crea uno nuevo si no existe.
        Útil para recuperar el carrito al abrir la app desde cualquier dispositivo.
        """
        cart = await self.repo.get_active_cart_for_user(user_id=user_id)
        
        if cart is None:
            # No tiene carrito activo (o expiró), crear uno nuevo
            cart = await self.repo.create_cart(user_id=user_id)
        
        return cart


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
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
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
            return self.repo.add_item(cart_id=cart_id, user_id=user_id, item=item)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class RemoveItem:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID, item_id: UUID) -> None:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        try:
            self.repo.remove_item(cart_id=cart_id, user_id=user_id, item_id=item_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class ListItems:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> list[CartItem]:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        return self.repo.list_items(cart_id=cart_id, user_id=user_id)


@dataclass
class Checkout:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> CartSession:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        try:
            return self.repo.checkout(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise
