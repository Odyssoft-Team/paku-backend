from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.store.domain.models import Addon, Category, PriceRule, Product, Species
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository


@dataclass
class AddonWithPrices:
    addon: Addon
    price_rules: List[PriceRule] = field(default_factory=list)


@dataclass
class ProductWithPrices:
    product: Product
    price_rules: List[PriceRule] = field(default_factory=list)


@dataclass
class ListCategories:
    repo: PostgresStoreRepository

    async def execute(self, *, species: Optional[Species] = None) -> List[Category]:
        return await self.repo.list_categories(species=species)


@dataclass
class ListProducts:
    repo: PostgresStoreRepository

    async def execute(
        self,
        *,
        category_slug: str,
        species: Optional[Species] = None,
        breed: Optional[str] = None,
    ) -> List[ProductWithPrices]:
        category = await self.repo.get_category_by_slug(category_slug)
        if not category or not category.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        products = await self.repo.list_products(category_id=category.id, species=species, breed=breed)
        result = []
        for p in products:
            price_rules = await self.repo.list_price_rules(target_id=p.id)
            result.append(ProductWithPrices(product=p, price_rules=price_rules))
        return result


@dataclass
class GetProduct:
    repo: PostgresStoreRepository

    async def execute(
        self, *, product_id: UUID, breed: Optional[str] = None
    ) -> tuple[ProductWithPrices, List[AddonWithPrices]]:
        product = await self.repo.get_product(product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        product_rules = await self.repo.list_price_rules(target_id=product_id)
        addons = await self.repo.list_addons(product_id=product_id, breed=breed)
        addons_with_prices: List[AddonWithPrices] = []
        for a in addons:
            addon_rules = await self.repo.list_price_rules(target_id=a.id)
            addons_with_prices.append(AddonWithPrices(addon=a, price_rules=addon_rules))
        return ProductWithPrices(product=product, price_rules=product_rules), addons_with_prices
