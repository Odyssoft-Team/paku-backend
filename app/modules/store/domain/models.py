from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Protocol
from uuid import UUID


class Species(str, Enum):
    dog = "dog"
    cat = "cat"


@dataclass(frozen=True)
class Category:
    id: UUID
    name: str
    slug: str
    species: Optional[Species]  # None = aplica a ambas especies
    is_active: bool


@dataclass(frozen=True)
class Product:
    id: UUID
    category_id: UUID
    name: str
    species: Species
    allowed_breeds: Optional[List[str]]
    is_active: bool
    description: Optional[str] = None


@dataclass(frozen=True)
class Addon:
    id: UUID
    product_id: UUID
    name: str
    species: Species
    allowed_breeds: Optional[List[str]]
    is_active: bool
    description: Optional[str] = None


@dataclass(frozen=True)
class PriceRule:
    id: UUID
    target_id: UUID       # product_id o addon_id
    target_type: str      # "product" | "addon"
    species: Species
    breed_category: str
    weight_min: float
    weight_max: Optional[float]
    price: float          # soles con decimales, ej: 120.00 (NO centavos)
    currency: str
    is_active: bool


class StoreRepository(Protocol):
    # --- categorías ---
    async def list_categories(self, *, species: Optional[Species] = None) -> List[Category]: ...
    async def get_category(self, category_id: UUID) -> Optional[Category]: ...
    async def get_category_by_slug(self, slug: str) -> Optional[Category]: ...
    async def create_category(self, *, name: str, slug: str, species: Optional[Species], is_active: bool) -> Category: ...
    async def update_category(self, category_id: UUID, patch: dict) -> Category: ...
    async def set_category_active(self, category_id: UUID, is_active: bool) -> Category: ...

    # --- productos ---
    async def list_products(self, *, category_id: UUID, species: Optional[Species] = None, breed: Optional[str] = None) -> List[Product]: ...
    async def get_product(self, product_id: UUID) -> Optional[Product]: ...
    async def create_product(self, *, category_id: UUID, name: str, description: Optional[str], species: Species, allowed_breeds: Optional[List[str]], is_active: bool) -> Product: ...
    async def update_product(self, product_id: UUID, patch: dict) -> Product: ...
    async def set_product_active(self, product_id: UUID, is_active: bool) -> Product: ...

    # --- addons ---
    async def list_addons(self, *, product_id: UUID, breed: Optional[str] = None) -> List[Addon]: ...
    async def get_addon(self, addon_id: UUID) -> Optional[Addon]: ...
    async def create_addon(self, *, product_id: UUID, name: str, description: Optional[str], species: Species, allowed_breeds: Optional[List[str]], is_active: bool) -> Addon: ...
    async def update_addon(self, addon_id: UUID, patch: dict) -> Addon: ...
    async def set_addon_active(self, addon_id: UUID, is_active: bool) -> Addon: ...

    # --- price rules ---
    async def list_price_rules(self, *, target_id: UUID) -> List[PriceRule]: ...
    async def create_price_rule(self, *, target_id: UUID, target_type: str, species: Species, breed_category: str, weight_min: float, weight_max: Optional[float], price: float, currency: str) -> PriceRule: ...
    async def update_price_rule(self, rule_id: UUID, patch: dict) -> PriceRule: ...
    async def price_for(self, *, target_id: UUID, target_type: str, species: Species, breed_category: str, weight: float) -> Optional[float]: ...
