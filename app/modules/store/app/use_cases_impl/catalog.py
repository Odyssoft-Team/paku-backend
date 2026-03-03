from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.store.domain.models import Addon, Category, Product, Species
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository


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
    ) -> List[Product]:
        category = await self.repo.get_category_by_slug(category_slug)
        if not category or not category.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return await self.repo.list_products(category_id=category.id, species=species, breed=breed)


@dataclass
class GetProduct:
    repo: PostgresStoreRepository

    async def execute(self, *, product_id: UUID, breed: Optional[str] = None) -> tuple[Product, List[Addon]]:
        product = await self.repo.get_product(product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        addons = await self.repo.list_addons(product_id=product_id, breed=breed)
        return product, addons
