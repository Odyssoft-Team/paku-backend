from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.commerce.domain.addons_rules import (
    ADDON_DESLANADO_ID,
    ADDON_DESMOTADO_ID,
    DESLANADO_REQUIRED_BREEDS,
    deslanado_applicable_breeds,
    desmotado_applicable_breeds,
)
from app.modules.commerce.domain.service import ServiceType, Species
from app.modules.commerce.infra.postgres_commerce_repository import PostgresCommerceRepository
from app.modules.pets.domain.pet import PetRepository

from .services import breed_allowed


def _normalize_breed(breed: Optional[str]) -> Optional[str]:
    if breed is None:
        return None
    normalized = str(breed).strip().lower()
    return normalized or None


# [TECH] Normaliza la raza a una categoría de pricing. Input: breed. Output: str. Flujo: precios/reglas.
# [NEGOCIO] Simplifica las razas en grupos para aplicar precios consistentes.
def _breed_category(breed: Optional[str]) -> str:
    if not breed or not str(breed).strip():
        return "mestizo"
    if str(breed).strip().lower() in {"husky", "labrador"}:
        return "official"
    return "otros"


@dataclass
# [TECH] Línea de precio (servicio y monto). Output: desglose. Flujo: precios.
# [NEGOCIO] Muestra el precio de cada parte del servicio para transparencia.
class QuoteLine:
    service_id: UUID
    name: str
    price: int


@dataclass
# [TECH] Resultado de cotización: base + addons + total + moneda. Output: QuoteResult. Flujo: precios/addons.
# [NEGOCIO] Resume cuánto pagará el cliente por el servicio y sus adicionales.
class QuoteResult:
    pet_id: UUID
    base: QuoteLine
    addons: List[QuoteLine]
    total: int
    currency: str = "PEN"


@dataclass
# [TECH] Calcula cotización del servicio base + addons para una mascota. Output: QuoteResult. Flujo: precios/addons/reglas.
# [NEGOCIO] Determina el total a cobrar al cliente según su mascota y lo que selecciona.
class Quote:
    repo: PostgresCommerceRepository
    pets_repo: PetRepository

    async def execute(
        self,
        *,
        pet_id: UUID,
        base_service_id: UUID,
        addon_ids: Optional[List[UUID]] = None,
    ) -> QuoteResult:
        pet = await self.pets_repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        raw_species = getattr(pet.species, "value", pet.species)
        pet_species = Species(str(raw_species))
        pet_breed = getattr(pet, "breed", None)
        pet_breed_norm = _normalize_breed(pet_breed)
        pet_weight = getattr(pet, "weight_kg", None)

        if pet_weight is None or float(pet_weight) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Pet weight_kg is required to quote",
            )

        requested_addons = set(addon_ids or [])
        if pet_breed_norm in DESLANADO_REQUIRED_BREEDS and ADDON_DESLANADO_ID not in requested_addons:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "addon_id": str(ADDON_DESLANADO_ID),
                    "reason": "required_for_breed",
                    "message": "Deslanado es obligatorio para esta raza",
                },
            )

        if ADDON_DESLANADO_ID in requested_addons and pet_breed_norm not in deslanado_applicable_breeds():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "addon_id": str(ADDON_DESLANADO_ID),
                    "reason": "not_applicable",
                    "message": "Deslanado no aplica para esta raza",
                },
            )

        if ADDON_DESMOTADO_ID in requested_addons and pet_breed_norm not in desmotado_applicable_breeds():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "addon_id": str(ADDON_DESMOTADO_ID),
                    "reason": "not_applicable",
                    "message": "Desmotado no aplica para esta raza",
                },
            )

        items = await self.repo.list_services_for_pet(pet)
        by_id = {s.id: s for s in items}

        base = by_id.get(base_service_id)
        if not base or base.type != ServiceType.base:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base_service_id")
        if not breed_allowed(base.allowed_breeds, pet_breed):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base service not applicable")

        breed_cat = _breed_category(pet_breed)
        weight = float(pet_weight)

        base_price = await self.repo.price_for(
            service_id=base.id,
            species=pet_species,
            breed_category=breed_cat,
            weight=weight,
        )
        base_line = QuoteLine(service_id=base.id, name=base.name, price=base_price.price)

        addons_out: List[QuoteLine] = []
        for addon_id in addon_ids or []:
            addon = by_id.get(addon_id)
            if not addon:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"addon_id": str(addon_id), "reason": "not_found"},
                )
            if addon.type != ServiceType.addon:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"addon_id": str(addon_id), "reason": "not_addon"},
                )
            if not breed_allowed(addon.allowed_breeds, pet_breed):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"addon_id": str(addon_id), "reason": "not_applicable"},
                )
            if base.id not in (addon.requires or []):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"addon_id": str(addon_id), "reason": "missing_requires"},
                )

            addon_price = await self.repo.price_for(
                service_id=addon.id,
                species=pet_species,
                breed_category=breed_cat,
                weight=weight,
            )
            addons_out.append(QuoteLine(service_id=addon.id, name=addon.name, price=addon_price.price))

        total = base_line.price + sum(a.price for a in addons_out)
        return QuoteResult(pet_id=pet_id, base=base_line, addons=addons_out, total=total)
