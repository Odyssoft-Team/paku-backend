from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.commerce.domain.service import Service, Species, ServiceType
from app.modules.commerce.infra.postgres_commerce_repository import PostgresCommerceRepository
from app.modules.pets.domain.pet import PetRepository


# [TECH] Regla: valida si una raza está permitida para un servicio. Output: bool. Flujo: reglas/catálogo.
# [NEGOCIO] Evita ofrecer servicios que no corresponden a la raza del cliente.
def breed_allowed(allowed_breeds: Optional[List[str]], breed: Optional[str]) -> bool:
    def _norm(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        v = value.strip().lower()
        return v or None

    if not allowed_breeds:
        return True
    breed_norm = _norm(breed)
    if breed_norm is None:
        return False
    allowed_norm = {_norm(b) for b in allowed_breeds}
    allowed_norm.discard(None)
    return breed_norm in allowed_norm


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
            if s.type == ServiceType.base and breed_allowed(s.allowed_breeds, pet_breed)
        ]
        addons = [
            s
            for s in items
            if s.type == ServiceType.addon and breed_allowed(s.allowed_breeds, pet_breed)
        ]

        out: List[AvailableService] = []
        for base in bases:
            base_addons = [a for a in addons if base.id in (a.requires or [])]
            out.append(AvailableService(base=base, available_addons=base_addons))
        return out
