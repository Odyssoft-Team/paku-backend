from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.store.domain.models import Addon, Category, Product, Species
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository
from app.modules.store.app.use_cases_impl.quote import _breed_category
from app.modules.pets.domain.pet import PetRepository


@dataclass
class ResolvedAddon:
    addon: Addon
    price: Optional[int]


@dataclass
class ResolvedProduct:
    product: Product
    price: Optional[int]


@dataclass
class ListCategories:
    repo: PostgresStoreRepository

    async def execute(self, *, species: Optional[Species] = None) -> List[Category]:
        return await self.repo.list_categories(species=species)


@dataclass
class ListProducts:
    repo: PostgresStoreRepository
    pets_repo: PetRepository

    async def execute(
        self,
        *,
        category_slug: str,
        pet_id: Optional[UUID] = None,
        species: Optional[Species] = None,
    ) -> List[ResolvedProduct]:
        category = await self.repo.get_category_by_slug(category_slug)
        if not category or not category.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        pet_species, breed_cat, weight = await _resolve_pet(self.pets_repo, pet_id)
        effective_species = pet_species or species

        products = await self.repo.list_products(category_id=category.id, species=effective_species)
        result = []
        for p in products:
            price = None
            if breed_cat is not None and weight is not None:
                price = await self.repo.price_for(
                    target_id=p.id,
                    target_type="product",
                    species=p.species,
                    breed_category=breed_cat,
                    weight=weight,
                )
            result.append(ResolvedProduct(product=p, price=price))
        return result


@dataclass
class GetProduct:
    repo: PostgresStoreRepository
    pets_repo: PetRepository

    async def execute(
        self, *, product_id: UUID, pet_id: Optional[UUID] = None
    ) -> tuple[ResolvedProduct, List[ResolvedAddon]]:
        product = await self.repo.get_product(product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        pet_species, breed_cat, weight = await _resolve_pet(self.pets_repo, pet_id)

        product_price = None
        if breed_cat is not None and weight is not None:
            product_price = await self.repo.price_for(
                target_id=product_id,
                target_type="product",
                species=product.species,
                breed_category=breed_cat,
                weight=weight,
            )

        addons = await self.repo.list_addons(product_id=product_id)
        resolved_addons: List[ResolvedAddon] = []
        for a in addons:
            addon_price = None
            if breed_cat is not None and weight is not None:
                addon_price = await self.repo.price_for(
                    target_id=a.id,
                    target_type="addon",
                    species=a.species,
                    breed_category=breed_cat,
                    weight=weight,
                )
            resolved_addons.append(ResolvedAddon(addon=a, price=addon_price))

        return ResolvedProduct(product=product, price=product_price), resolved_addons


async def _resolve_pet(
    pets_repo: PetRepository, pet_id: Optional[UUID]
) -> tuple[Optional[Species], Optional[str], Optional[float]]:
    """Returns (species, breed_category, weight_kg) for the pet, or (None, None, None) if no pet."""
    if pet_id is None:
        return None, None, None
    pet = await pets_repo.get_by_id(pet_id)
    if not pet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
    weight = float(pet.weight_kg) if pet.weight_kg else None
    breed_cat = _breed_category(pet.breed) if weight is not None else None
    raw_species = getattr(pet.species, "value", pet.species)
    return Species(str(raw_species)), breed_cat, weight
