from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.commerce.domain.service import Service, ServiceType, Species


@dataclass(frozen=True)
class PriceResult:
    price: int
    currency: str


_commerce_seeded = False


class PostgresCommerceRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def _ensure_ready(self) -> None:
        from app.modules.commerce.infra.models import ensure_commerce_schema

        await ensure_commerce_schema(self._engine)
        await self.seed_if_empty()

    async def seed_if_empty(self) -> None:
        global _commerce_seeded
        if _commerce_seeded:
            return

        from app.modules.commerce.infra.models import PriceRuleModel, ServiceModel, utcnow

        await self._session.flush()

        res = await self._session.execute(select(ServiceModel.id).limit(1))
        if res.first() is not None:
            _commerce_seeded = True
            return

        now = utcnow()

        base_dog_bath = UUID("11111111-1111-1111-1111-111111111111")
        addon_dog_nails = UUID("22222222-2222-2222-2222-222222222222")
        base_cat_groom = UUID("33333333-3333-3333-3333-333333333333")
        addon_dog_teeth = UUID("44444444-4444-4444-4444-444444444444")
        addon_dog_haircut = UUID("55555555-5555-5555-5555-555555555555")

        services = [
            ServiceModel(
                id=base_dog_bath,
                name="Bano base (perro)",
                type=ServiceType.base.value,
                species=Species.dog.value,
                allowed_breeds=None,
                requires=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            ServiceModel(
                id=addon_dog_nails,
                name="Corte de unas (addon)",
                type=ServiceType.addon.value,
                species=Species.dog.value,
                allowed_breeds=["husky", "labrador"],
                requires=[str(base_dog_bath)],
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            ServiceModel(
                id=base_cat_groom,
                name="Aseo base (gato)",
                type=ServiceType.base.value,
                species=Species.cat.value,
                allowed_breeds=None,
                requires=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            ServiceModel(
                id=addon_dog_teeth,
                name="Limpieza dental (addon)",
                type=ServiceType.addon.value,
                species=Species.dog.value,
                allowed_breeds=None,
                requires=[str(base_dog_bath)],
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            ServiceModel(
                id=addon_dog_haircut,
                name="Corte de pelo",
                type=ServiceType.addon.value,
                species=Species.dog.value,
                allowed_breeds=["husky", "labrador"],
                requires=[str(base_dog_bath)],
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
        ]

        self._session.add_all(services)

        def _rule(
            *,
            service_id: UUID,
            species: Species,
            breed_category: str,
            weight_min: float,
            weight_max: float | None,
            price: int,
        ) -> PriceRuleModel:
            return PriceRuleModel(
                service_id=service_id,
                species=species.value,
                breed_category=breed_category,
                weight_min=weight_min,
                weight_max=weight_max,
                price=Decimal(price),
                currency="PEN",
                is_active=True,
                created_at=now,
                updated_at=now,
            )

        rules = [
            _rule(service_id=base_dog_bath, species=Species.dog, breed_category="mestizo", weight_min=0, weight_max=10, price=50),
            _rule(service_id=base_dog_bath, species=Species.dog, breed_category="mestizo", weight_min=10, weight_max=25, price=70),
            _rule(service_id=base_dog_bath, species=Species.dog, breed_category="mestizo", weight_min=25, weight_max=None, price=90),
            _rule(service_id=base_dog_bath, species=Species.dog, breed_category="official", weight_min=0, weight_max=10, price=60),
            _rule(service_id=base_cat_groom, species=Species.cat, breed_category="mestizo", weight_min=0, weight_max=10, price=45),
            _rule(service_id=addon_dog_haircut, species=Species.dog, breed_category="mestizo", weight_min=0, weight_max=None, price=55),
            _rule(service_id=addon_dog_nails, species=Species.dog, breed_category="mestizo", weight_min=0, weight_max=None, price=15),
            _rule(service_id=addon_dog_teeth, species=Species.dog, breed_category="mestizo", weight_min=0, weight_max=None, price=25),
        ]

        self._session.add_all(rules)

        try:
            await self._session.commit()
        except IntegrityError:
            # Seed puede correr concurrentemente en multi-worker.
            # Si otro worker insertó primero, el commit puede fallar por PK duplicada.
            await self._session.rollback()
            res = await self._session.execute(select(ServiceModel.id).limit(1))
            if res.first() is None:
                raise
        _commerce_seeded = True

    async def list_services(self, *, species: Species, breed: Optional[str] = None) -> List[Service]:
        await self._ensure_ready()

        from app.modules.commerce.infra.models import ServiceModel

        stmt = select(ServiceModel).where(
            and_(
                ServiceModel.is_active.is_(True),
                ServiceModel.species == species.value,
            )
        )
        res = await self._session.execute(stmt)
        rows = res.scalars().all()

        out: List[Service] = []
        for r in rows:
            allowed = r.allowed_breeds
            if allowed:
                if breed is None or breed not in allowed:
                    continue

            requires: Optional[List[UUID]] = None
            if r.requires:
                requires = [UUID(x) for x in r.requires]

            out.append(
                Service(
                    id=r.id,
                    name=r.name,
                    type=ServiceType(r.type),
                    species=Species(r.species),
                    allowed_breeds=r.allowed_breeds,
                    requires=requires,
                    is_active=r.is_active,
                )
            )
        return out

    async def list_services_for_pet(self, pet) -> List[Service]:
        raw_species = getattr(pet.species, "value", pet.species)
        pet_species = Species(str(raw_species))
        pet_breed = getattr(pet, "breed", None)
        return await self.list_services(species=pet_species, breed=pet_breed)

    async def get_service(self, service_id: UUID) -> Optional[Service]:
        await self._ensure_ready()

        from app.modules.commerce.infra.models import ServiceModel

        model = await self._session.get(ServiceModel, service_id)
        if model is None:
            return None

        requires: Optional[List[UUID]] = None
        if model.requires:
            requires = [UUID(x) for x in model.requires]

        return Service(
            id=model.id,
            name=model.name,
            type=ServiceType(model.type),
            species=Species(model.species),
            allowed_breeds=model.allowed_breeds,
            requires=requires,
            is_active=model.is_active,
        )

    async def price_for(
        self,
        *,
        service_id: UUID,
        species: Species,
        breed_category: str,
        weight: float,
    ) -> PriceResult:
        await self._ensure_ready()

        from app.modules.commerce.infra.models import PriceRuleModel

        async def _find(cat: str) -> Optional[PriceRuleModel]:
            stmt = (
                select(PriceRuleModel)
                .where(
                    and_(
                        PriceRuleModel.is_active.is_(True),
                        PriceRuleModel.service_id == service_id,
                        PriceRuleModel.species == species.value,
                        PriceRuleModel.breed_category == cat,
                        PriceRuleModel.weight_min <= weight,
                        (PriceRuleModel.weight_max.is_(None) | (PriceRuleModel.weight_max >= weight)),
                    )
                )
                .order_by(PriceRuleModel.weight_min.desc())
            )
            res = await self._session.execute(stmt)
            return res.scalars().first()

        rule = await _find(breed_category)
        if rule is None and breed_category != "mestizo":
            rule = await _find("mestizo")

        if rule is None:
            return PriceResult(price=0, currency="PEN")

        return PriceResult(price=int(Decimal(rule.price)), currency=rule.currency)

    async def quote(
        self,
        *,
        pet,
        base_service_id: UUID,
        addon_ids: Optional[List[UUID]] = None,
        breed_category: str,
        weight: float,
    ):
        from app.modules.commerce.app.use_cases import QuoteLine, QuoteResult

        services = await self.list_services_for_pet(pet)
        by_id = {s.id: s for s in services}

        base = by_id.get(base_service_id)
        if not base or base.type != ServiceType.base:
            raise ValueError("invalid_base")

        base_price = await self.price_for(
            service_id=base.id,
            species=base.species,
            breed_category=breed_category,
            weight=weight,
        )
        base_line = QuoteLine(service_id=base.id, name=base.name, price=base_price.price)

        addons_out: List[QuoteLine] = []
        for addon_id in addon_ids or []:
            addon = by_id.get(addon_id)
            if not addon:
                raise ValueError("addon_not_found")
            if addon.type != ServiceType.addon:
                raise ValueError("addon_not_addon")
            if base.id not in (addon.requires or []):
                raise ValueError("addon_missing_requires")

            addon_price = await self.price_for(
                service_id=addon.id,
                species=addon.species,
                breed_category=breed_category,
                weight=weight,
            )
            addons_out.append(QuoteLine(service_id=addon.id, name=addon.name, price=addon_price.price))

        total = base_line.price + sum(a.price for a in addons_out)
        return QuoteResult(pet_id=pet.id, base=base_line, addons=addons_out, total=total)
