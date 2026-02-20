from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Protocol, Union
from uuid import UUID, uuid4


# [TECH]
# Enum defining cart lifecycle states with TTL behavior.
#
# [NATURAL/BUSINESS]
# Estados del carrito: activo, finalizado, expirado o cancelado.
class CartStatus(str, Enum):
    active = "active"
    checked_out = "checked_out"
    expired = "expired"
    cancelled = "cancelled"


# [TECH]
# Enum for cart item types: services or products.
#
# [NATURAL/BUSINESS]
# Tipos de items: servicios base, adicionales o productos.
class CartItemKind(str, Enum):
    service_base = "service_base"
    service_addon = "service_addon"
    product = "product"


# [TECH]
# Immutable cart session with TTL and status tracking.
#
# [NATURAL/BUSINESS]
# Carrito de compra con fecha de expiración y estado.
@dataclass(frozen=True)
class CartSession:
    id: UUID
    user_id: UUID
    status: CartStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    # [TECH]
    # Factory creating active cart with configurable TTL.
    #
    # [NATURAL/BUSINESS]
    # Crea un carrito nuevo que expira en horas.
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


# [TECH]
# Immutable cart item with typed reference and metadata.
#
# [NATURAL/BUSINESS]
# Producto o servicio agregado al carrito.
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

    # [TECH]
    # Factory creating cart item with UUID and defaults.
    #
    # [NATURAL/BUSINESS]
    # Crea un nuevo item para el carrito.
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


# [TECH]
# Repository interface for cart and item persistence.
#
# [NATURAL/BUSINESS]
# Guarda y gestiona carritos y sus items.
class CartRepository(Protocol):
    def create_cart(self, user_id: UUID) -> CartSession:
        ...

    def get_cart(self, cart_id: UUID, user_id: UUID) -> CartSession:
        ...

    def get_active_cart_for_user(self, user_id: UUID) -> Optional[CartSession]:
        ...

    def add_item(self, cart_id: UUID, user_id: UUID, item: CartItem) -> CartItem:
        ...

    def remove_item(self, cart_id: UUID, user_id: UUID, item_id: UUID) -> None:
        ...

    def list_items(self, cart_id: UUID, user_id: UUID) -> list[CartItem]:
        ...

    def checkout(self, cart_id: UUID, user_id: UUID) -> CartSession:
        ...
