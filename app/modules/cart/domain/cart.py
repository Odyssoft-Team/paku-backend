from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Protocol, Union
from uuid import UUID, uuid4


class CartStatus(str, Enum):
    active = "active"
    checked_out = "checked_out"
    expired = "expired"
    cancelled = "cancelled"


class CartItemKind(str, Enum):
    service_base = "service_base"
    service_addon = "service_addon"
    product = "product"


@dataclass(frozen=True)
class CartSession:
    id: UUID
    user_id: UUID
    status: CartStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def new(*, user_id: UUID, ttl_hours: int = 2) -> "CartSession":
        now = datetime.now(timezone.utc)
        return CartSession(
            id=uuid4(),
            user_id=user_id,
            status=CartStatus.active,
            expires_at=now + timedelta(hours=ttl_hours),
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True)
class CartItem:
    id: UUID
    cart_id: UUID
    kind: CartItemKind
    ref_id: Union[UUID, str]
    name: Optional[str]
    qty: int
    unit_price: Optional[float]
    meta: Optional[dict[str, Any]]

    @staticmethod
    def new(
        *,
        cart_id: UUID,
        kind: CartItemKind,
        ref_id: Union[UUID, str],
        name: Optional[str] = None,
        qty: int = 1,
        unit_price: Optional[float] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> "CartItem":
        return CartItem(
            id=uuid4(),
            cart_id=cart_id,
            kind=kind,
            ref_id=ref_id,
            name=name,
            qty=qty,
            unit_price=unit_price,
            meta=meta,
        )


class CartRepository(Protocol):
    def create_cart(self, user_id: UUID) -> CartSession:
        ...

    def get_cart(self, cart_id: UUID, user_id: UUID) -> CartSession:
        ...

    def add_item(self, cart_id: UUID, user_id: UUID, item: CartItem) -> CartItem:
        ...

    def remove_item(self, cart_id: UUID, user_id: UUID, item_id: UUID) -> None:
        ...

    def list_items(self, cart_id: UUID, user_id: UUID) -> list[CartItem]:
        ...

    def checkout(self, cart_id: UUID, user_id: UUID) -> CartSession:
        ...
