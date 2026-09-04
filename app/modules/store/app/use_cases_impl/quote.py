from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.store.domain.models import Species
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository
from app.modules.pets.domain.pet import PetRepository

_MIXED_BREED_SUFFIX = "_mixed"


def _breed_category(breed_id: Optional[str], breed_name: Optional[str]) -> str:
    """Categoriza la raza de la mascota para el pricing.

    breed_id viene validado por FK contra `breeds.id` (o es None si el usuario
    escribió una raza que no está en el catálogo, o no seleccionó ninguna).

    - "mestizo": sin breed_id ni breed_name, o breed_id mestizo (ej. "dog_mixed"/"cat_mixed")
    - "official": breed_id apunta a una raza reconocida del catálogo
    - "otros": hay breed_name pero no matcheó ninguna raza del catálogo (breed_id vacío)
    """
    if breed_id:
        return "mestizo" if breed_id.strip().lower().endswith(_MIXED_BREED_SUFFIX) else "official"
    return "otros" if breed_name and str(breed_name).strip() else "mestizo"


@dataclass
class QuoteLine:
    target_id: UUID
    name: str
    price: float   # soles con decimales, ej: 120.0


@dataclass
class QuoteResult:
    pet_id: UUID
    product: QuoteLine
    addons: List[QuoteLine] = field(default_factory=list)
    total: float = 0.0   # soles con decimales
    currency: str = "PEN"


@dataclass
class Quote:
    repo: PostgresStoreRepository
    pets_repo: PetRepository

    async def execute(
        self,
        *,
        pet_id: UUID,
        product_id: UUID,
        addon_ids: Optional[List[UUID]] = None,
    ) -> QuoteResult:
        pet = await self.pets_repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        pet_weight = getattr(pet, "weight_kg", None)
        if pet_weight is None or float(pet_weight) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Pet weight_kg is required to quote",
            )

        raw_species = getattr(pet.species, "value", pet.species)
        pet_species = Species(str(raw_species))
        breed_cat = _breed_category(getattr(pet, "breed_id", None), getattr(pet, "breed_name", None))
        weight = float(pet_weight)

        product = await self.repo.get_product(product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        if product.species != pet_species:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product species does not match pet species",
            )

        product_price = await self.repo.price_for(
            target_id=product.id,
            target_type="product",
            species=pet_species,
            breed_category=breed_cat,
            weight=weight,
        )
        if product_price is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No price rule found for this product and pet",
            )

        product_line = QuoteLine(target_id=product.id, name=product.name, price=product_price)

        addons_out: List[QuoteLine] = []
        for addon_id in addon_ids or []:
            addon = await self.repo.get_addon(addon_id)
            if not addon or not addon.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"addon_id": str(addon_id), "reason": "not_found"},
                )
            if addon.product_id != product.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"addon_id": str(addon_id), "reason": "not_in_product"},
                )

            addon_price = await self.repo.price_for(
                target_id=addon.id,
                target_type="addon",
                species=pet_species,
                breed_category=breed_cat,
                weight=weight,
            )
            if addon_price is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"addon_id": str(addon_id), "reason": "no_price_rule"},
                )
            addons_out.append(QuoteLine(target_id=addon.id, name=addon.name, price=addon_price))

        total = product_line.price + sum(a.price for a in addons_out)
        return QuoteResult(pet_id=pet_id, product=product_line, addons=addons_out, total=total)
