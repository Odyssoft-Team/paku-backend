from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.store.domain.models import Addon, Category, PriceRule, Product, Species
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository


def _not_found(detail: str):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


# ------------------------------------------------------------------
# Categorías
# ------------------------------------------------------------------

@dataclass
class ListAllCategories:
    repo: PostgresStoreRepository

    async def execute(self) -> List[Category]:
        return await self.repo.list_categories()


@dataclass
class CreateCategory:
    repo: PostgresStoreRepository

    async def execute(
        self, *, name: str, slug: str, species: Optional[Species], is_active: bool = True
    ) -> Category:
        return await self.repo.create_category(name=name, slug=slug, species=species, is_active=is_active)


@dataclass
class UpdateCategory:
    repo: PostgresStoreRepository

    async def execute(self, category_id: UUID, *, name: Optional[str] = None, species: Optional[Species] = None) -> Category:
        patch = {}
        if name is not None:
            patch["name"] = name
        if species is not None:
            patch["species"] = species
        try:
            return await self.repo.update_category(category_id, patch)
        except ValueError as exc:
            if str(exc) == "category_not_found":
                _not_found("Category not found")
            raise


@dataclass
class ToggleCategory:
    repo: PostgresStoreRepository

    async def execute(self, category_id: UUID, *, is_active: bool) -> Category:
        try:
            return await self.repo.set_category_active(category_id, is_active)
        except ValueError as exc:
            if str(exc) == "category_not_found":
                _not_found("Category not found")
            raise


# ------------------------------------------------------------------
# Productos
# ------------------------------------------------------------------

@dataclass
class ListAllProducts:
    repo: PostgresStoreRepository

    async def execute(self, *, category_id: UUID) -> List[Product]:
        return await self.repo.list_products(category_id=category_id)


@dataclass
class CreateProduct:
    repo: PostgresStoreRepository

    async def execute(
        self,
        *,
        category_id: UUID,
        name: str,
        species: Species,
        allowed_breeds: Optional[List[str]],
        is_active: bool = True,
    ) -> Product:
        category = await self.repo.get_category(category_id)
        if not category:
            _not_found("Category not found")
        return await self.repo.create_product(
            category_id=category_id,
            name=name,
            species=species,
            allowed_breeds=allowed_breeds,
            is_active=is_active,
        )


@dataclass
class UpdateProduct:
    repo: PostgresStoreRepository

    async def execute(
        self, product_id: UUID, *, name: Optional[str] = None, allowed_breeds: Optional[List[str]] = None
    ) -> Product:
        patch = {}
        if name is not None:
            patch["name"] = name
        if allowed_breeds is not None:
            patch["allowed_breeds"] = allowed_breeds
        try:
            return await self.repo.update_product(product_id, patch)
        except ValueError as exc:
            if str(exc) == "product_not_found":
                _not_found("Product not found")
            raise


@dataclass
class ToggleProduct:
    repo: PostgresStoreRepository

    async def execute(self, product_id: UUID, *, is_active: bool) -> Product:
        try:
            return await self.repo.set_product_active(product_id, is_active)
        except ValueError as exc:
            if str(exc) == "product_not_found":
                _not_found("Product not found")
            raise


# ------------------------------------------------------------------
# Addons
# ------------------------------------------------------------------

@dataclass
class ListAllAddons:
    repo: PostgresStoreRepository

    async def execute(self, *, product_id: UUID) -> List[Addon]:
        return await self.repo.list_addons(product_id=product_id)


@dataclass
class CreateAddon:
    repo: PostgresStoreRepository

    async def execute(
        self,
        *,
        product_id: UUID,
        name: str,
        species: Species,
        allowed_breeds: Optional[List[str]],
        is_active: bool = True,
    ) -> Addon:
        product = await self.repo.get_product(product_id)
        if not product:
            _not_found("Product not found")
        return await self.repo.create_addon(
            product_id=product_id,
            name=name,
            species=species,
            allowed_breeds=allowed_breeds,
            is_active=is_active,
        )


@dataclass
class UpdateAddon:
    repo: PostgresStoreRepository

    async def execute(
        self, addon_id: UUID, *, name: Optional[str] = None, allowed_breeds: Optional[List[str]] = None
    ) -> Addon:
        patch = {}
        if name is not None:
            patch["name"] = name
        if allowed_breeds is not None:
            patch["allowed_breeds"] = allowed_breeds
        try:
            return await self.repo.update_addon(addon_id, patch)
        except ValueError as exc:
            if str(exc) == "addon_not_found":
                _not_found("Addon not found")
            raise


@dataclass
class ToggleAddon:
    repo: PostgresStoreRepository

    async def execute(self, addon_id: UUID, *, is_active: bool) -> Addon:
        try:
            return await self.repo.set_addon_active(addon_id, is_active)
        except ValueError as exc:
            if str(exc) == "addon_not_found":
                _not_found("Addon not found")
            raise


# ------------------------------------------------------------------
# Price Rules
# ------------------------------------------------------------------

@dataclass
class ListPriceRules:
    repo: PostgresStoreRepository

    async def execute(self, *, target_id: UUID) -> List[PriceRule]:
        return await self.repo.list_price_rules(target_id=target_id)


@dataclass
class CreatePriceRule:
    repo: PostgresStoreRepository

    async def execute(
        self,
        *,
        target_id: UUID,
        target_type: str,
        species: Species,
        breed_category: str,
        weight_min: float,
        weight_max: Optional[float],
        price: int,
        currency: str = "PEN",
    ) -> PriceRule:
        _VALID_BREED_CATEGORIES = {"official", "otros", "mestizo"}
        if breed_category not in _VALID_BREED_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"breed_category_invalid: debe ser uno de {sorted(_VALID_BREED_CATEGORIES)}",
            )
        if price < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="price_invalid: el precio no puede ser negativo",
            )
        if weight_max is not None and weight_max <= weight_min:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="weight_range_invalid: weight_max debe ser mayor que weight_min",
            )
        if target_type not in ("product", "addon"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="target_type must be 'product' or 'addon'",
            )
        return await self.repo.create_price_rule(
            target_id=target_id,
            target_type=target_type,
            species=species,
            breed_category=breed_category,
            weight_min=weight_min,
            weight_max=weight_max,
            price=price,
            currency=currency,
        )


@dataclass
class UpdatePriceRule:
    repo: PostgresStoreRepository

    async def execute(
        self,
        rule_id: UUID,
        *,
        price: Optional[int] = None,
        weight_min: Optional[float] = None,
        weight_max: Optional[float] = None,
        is_active: Optional[bool] = None,
    ) -> PriceRule:
        patch = {}
        if price is not None:
            if price < 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="price_invalid: el precio no puede ser negativo",
                )
            patch["price"] = price
        if weight_min is not None:
            patch["weight_min"] = weight_min
        if weight_max is not None:
            patch["weight_max"] = weight_max
        if is_active is not None:
            patch["is_active"] = is_active
        try:
            return await self.repo.update_price_rule(rule_id, patch)
        except ValueError as exc:
            if str(exc) == "price_rule_not_found":
                _not_found("Price rule not found")
            raise
