from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItemKind, CartRepository, CartSession, CartStatus

from .common import _is_kind, _meta_dict, _raise_cart_error


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

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> CartSession:
        try:
            cart = await self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        try:
            return await self.repo.checkout(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


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

        if base_services:
            base_ref_id = str(base_services[0].ref_id)

            for item in items:
                if _is_kind(getattr(item, "kind", None), CartItemKind.service_addon):
                    meta = _meta_dict(getattr(item, "meta", None))
                    requires_base = meta.get("requires_base")

                    if requires_base and str(requires_base) != base_ref_id:
                        errors.append(
                            f"Addon '{item.name}' requires base service '{requires_base}', "
                            f"but cart has '{base_ref_id}'"
                        )

        if total == 0:
            warnings.append("Total is 0. Please verify prices.")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total": total,
        }
