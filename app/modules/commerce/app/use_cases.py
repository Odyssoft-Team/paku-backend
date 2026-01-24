from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.commerce.domain.service import Service, Species, ServiceType
from app.modules.commerce.infra.postgres_commerce_repository import PostgresCommerceRepository
from app.modules.pets.domain.pet import PetRepository


@dataclass
# [TECH] Filtra catálogo por especie y reglas de raza. Input: species/breed. Output: List[Service].
# [NEGOCIO] Devuelve los servicios que realmente se pueden ofrecer a esa mascota.
class ListServices:
    repo: PostgresCommerceRepository

    async def execute(self, *, species: Species, breed: Optional[str] = None) -> List[Service]:
        return await self.repo.list_services(species=species, breed=breed)


@dataclass
# [TECH] Estructura de salida: servicio base + addons aplicables. Flujo: catálogo/addons.
# [NEGOCIO] Agrupa el servicio principal con los adicionales que el cliente puede elegir.
class AvailableService:
    base: Service
    available_addons: List[Service]


# [TECH] Regla: valida si una raza está permitida para un servicio. Output: bool. Flujo: reglas/catálogo.
# [NEGOCIO] Evita ofrecer servicios que no corresponden a la raza del cliente.
def _breed_allowed(allowed_breeds: Optional[List[str]], breed: Optional[str]) -> bool:
    if not allowed_breeds:
        return True
    if breed is None:
        return False
    return breed in allowed_breeds


@dataclass
# [TECH] Lista servicios base y addons aplicables para una mascota. Input: pet_id. Output: List[AvailableService].
# [NEGOCIO] Indica qué combinaciones de servicio + adicionales puede contratar el cliente.
class ListAvailableServices:
    repo: PostgresCommerceRepository
    pets_repo: PetRepository

    async def execute(self, *, pet_id: UUID) -> List[AvailableService]:
        pet = await self.pets_repo.get_by_id(pet_id)
        if not pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        pet_breed = getattr(pet, "breed", None)

        items = await self.repo.list_services_for_pet(pet)
        bases = [
            s
            for s in items
            if s.type == ServiceType.base and _breed_allowed(s.allowed_breeds, pet_breed)
        ]
        addons = [
            s
            for s in items
            if s.type == ServiceType.addon and _breed_allowed(s.allowed_breeds, pet_breed)
        ]

        out: List[AvailableService] = []
        for base in bases:
            base_addons = [a for a in addons if base.id in (a.requires or [])]
            out.append(AvailableService(base=base, available_addons=base_addons))
        return out


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


# [TECH] Normaliza la raza a una categoría de pricing. Input: breed. Output: str. Flujo: precios/reglas.
# [NEGOCIO] Simplifica las razas en grupos para aplicar precios consistentes.
def _breed_category(breed: Optional[str]) -> str:
    if not breed:
        return "mestizo"
    if breed.lower() in {"husky", "labrador"}:
        return "official"
    return "otros"


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
        pet_weight = getattr(pet, "weight_kg", None)

        items = await self.repo.list_services_for_pet(pet)
        by_id = {s.id: s for s in items}

        base = by_id.get(base_service_id)
        if not base or base.type != ServiceType.base:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base_service_id")
        if not _breed_allowed(base.allowed_breeds, pet_breed):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base service not applicable")

        breed_cat = _breed_category(pet_breed)
        weight = float(pet_weight or 0)

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
            if not _breed_allowed(addon.allowed_breeds, pet_breed):
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
