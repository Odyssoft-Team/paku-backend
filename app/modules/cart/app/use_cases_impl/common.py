from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItemKind


def _kind_value(kind: Any) -> str:
    return str(getattr(kind, "value", kind))


def _is_kind(kind: Any, expected: CartItemKind) -> bool:
    return _kind_value(kind) == expected.value


def _meta_dict(meta: Any) -> dict[str, Any]:
    return meta if isinstance(meta, dict) else {}


def _raise_cart_error(code: str) -> None:
    if code == "cart_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    if code == "cart_not_active":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Cart is not active (expired/checked out/cancelled)",
        )
    if code == "item_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if code == "invalid_cart_item":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cart item")
    if code == "multiple_base_services":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot have multiple base services in cart",
        )
