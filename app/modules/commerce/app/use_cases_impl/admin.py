from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.commerce.domain.service import PriceRule, Service, ServiceType, Species
from app.modules.commerce.infra.postgres_commerce_repository import PostgresCommerceRepository


@dataclass
class ListAllServices:
    repo: PostgresCommerceRepository

    async def execute(self) -> List[Service]:
        return await self.repo.list_all_services()


@dataclass
class CreateService:
    repo: PostgresCommerceRepository

    async def execute(
        self,
        *,
        name: str,
        type: ServiceType,
        species: Species,
        allowed_breeds: Optional[List[str]],
        requires: Optional[List[UUID]],
        is_active: bool = True,
    ) -> Service:
        if type == ServiceType.addon and not requires:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="addon_requires_service: un addon debe declarar al menos un servicio en 'requires'",
            )
        return await self.repo.create_service(
            name=name,
            type=type,
            species=species,
            allowed_breeds=allowed_breeds,
            requires=requires,
            is_active=is_active,
        )


@dataclass
class UpdateService:
    repo: PostgresCommerceRepository

    async def execute(
        self,
        service_id: UUID,
        *,
        name: Optional[str] = None,
        allowed_breeds: Optional[List[str]] = None,
        requires: Optional[List[UUID]] = None,
    ) -> Service:
        patch = {}
        if name is not None:
            patch["name"] = name
        if allowed_breeds is not None:
            patch["allowed_breeds"] = allowed_breeds
        if requires is not None:
            patch["requires"] = requires

        try:
            return await self.repo.update_service(service_id, patch)
        except ValueError as exc:
            if str(exc) == "service_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found") from exc
            raise


@dataclass
class ToggleService:
    repo: PostgresCommerceRepository

    async def execute(self, service_id: UUID, *, is_active: bool) -> Service:
        try:
            return await self.repo.set_service_active(service_id, is_active)
        except ValueError as exc:
            if str(exc) == "service_not_found":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found") from exc
            raise


@dataclass
class ListPriceRules:
    repo: PostgresCommerceRepository

    async def execute(self, service_id: UUID) -> List[PriceRule]:
        return await self.repo.list_price_rules(service_id)


@dataclass
class CreatePriceRule:
    repo: PostgresCommerceRepository

    async def execute(
        self,
        *,
        service_id: UUID,
        species: Species,
        breed_category: str,
        weight_min: float,
        weight_max: Optional[float],
        price: int,
        currency: str = "PEN",
    ) -> PriceRule:
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
        return await self.repo.create_price_rule(
            service_id=service_id,
            species=species,
            breed_category=breed_category,
            weight_min=weight_min,
            weight_max=weight_max,
            price=price,
            currency=currency,
        )


@dataclass
class UpdatePriceRule:
    repo: PostgresCommerceRepository

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
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price rule not found") from exc
            raise
