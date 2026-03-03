from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.store.domain.models import Addon, Category, PriceRule, Product, Species


def _breed_allowed(allowed_breeds: Optional[List[str]], breed: Optional[str]) -> bool:
    if not allowed_breeds:
        return True
    if not breed:
        return False
    breed_norm = breed.strip().lower()
    return breed_norm in {b.strip().lower() for b in allowed_breeds}


class PostgresStoreRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    # ------------------------------------------------------------------
    # Helpers de mapeo
    # ------------------------------------------------------------------

    def _to_category(self, r) -> Category:
        return Category(
            id=r.id,
            name=r.name,
            slug=r.slug,
            species=Species(r.species) if r.species else None,
            is_active=r.is_active,
        )

    def _to_product(self, r) -> Product:
        return Product(
            id=r.id,
            category_id=r.category_id,
            name=r.name,
            species=Species(r.species),
            allowed_breeds=r.allowed_breeds,
            is_active=r.is_active,
        )

    def _to_addon(self, r) -> Addon:
        return Addon(
            id=r.id,
            product_id=r.product_id,
            name=r.name,
            species=Species(r.species),
            allowed_breeds=r.allowed_breeds,
            is_active=r.is_active,
        )

    def _to_price_rule(self, r) -> PriceRule:
        return PriceRule(
            id=r.id,
            target_id=r.target_id,
            target_type=r.target_type,
            species=Species(r.species),
            breed_category=r.breed_category,
            weight_min=r.weight_min,
            weight_max=r.weight_max,
            price=int(r.price),
            currency=r.currency,
            is_active=r.is_active,
        )

    # ------------------------------------------------------------------
    # Categorías
    # ------------------------------------------------------------------

    async def list_categories(self, *, species: Optional[Species] = None) -> List[Category]:
        from app.modules.store.infra.db_models import CategoryModel

        stmt = select(CategoryModel).where(CategoryModel.is_active.is_(True))
        if species is not None:
            stmt = stmt.where(
                (CategoryModel.species == species.value) | (CategoryModel.species.is_(None))
            )
        result = await self._session.execute(stmt)
        return [self._to_category(r) for r in result.scalars().all()]

    async def get_category(self, category_id: UUID) -> Optional[Category]:
        from app.modules.store.infra.db_models import CategoryModel

        row = await self._session.get(CategoryModel, category_id)
        return self._to_category(row) if row else None

    async def get_category_by_slug(self, slug: str) -> Optional[Category]:
        from app.modules.store.infra.db_models import CategoryModel

        result = await self._session.execute(
            select(CategoryModel).where(CategoryModel.slug == slug)
        )
        row = result.scalar_one_or_none()
        return self._to_category(row) if row else None

    async def create_category(
        self, *, name: str, slug: str, species: Optional[Species], is_active: bool = True
    ) -> Category:
        from app.modules.store.infra.db_models import CategoryModel, _utcnow

        now = _utcnow()
        row = CategoryModel(
            name=name,
            slug=slug,
            species=species.value if species else None,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_category(row)

    async def update_category(self, category_id: UUID, patch: dict) -> Category:
        from app.modules.store.infra.db_models import CategoryModel, _utcnow

        row = await self._session.get(CategoryModel, category_id)
        if row is None:
            raise ValueError("category_not_found")
        for key, value in patch.items():
            if key == "species":
                row.species = value.value if value else None
            else:
                setattr(row, key, value)
        row.updated_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_category(row)

    async def set_category_active(self, category_id: UUID, is_active: bool) -> Category:
        from app.modules.store.infra.db_models import CategoryModel, _utcnow

        row = await self._session.get(CategoryModel, category_id)
        if row is None:
            raise ValueError("category_not_found")
        row.is_active = is_active
        row.updated_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_category(row)

    # ------------------------------------------------------------------
    # Productos
    # ------------------------------------------------------------------

    async def list_products(
        self,
        *,
        category_id: UUID,
        species: Optional[Species] = None,
        breed: Optional[str] = None,
    ) -> List[Product]:
        from app.modules.store.infra.db_models import ProductModel

        stmt = select(ProductModel).where(
            ProductModel.category_id == category_id,
            ProductModel.is_active.is_(True),
        )
        if species is not None:
            stmt = stmt.where(ProductModel.species == species.value)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        if breed is not None:
            rows = [r for r in rows if _breed_allowed(r.allowed_breeds, breed)]

        return [self._to_product(r) for r in rows]

    async def get_product(self, product_id: UUID) -> Optional[Product]:
        from app.modules.store.infra.db_models import ProductModel

        row = await self._session.get(ProductModel, product_id)
        return self._to_product(row) if row else None

    async def create_product(
        self,
        *,
        category_id: UUID,
        name: str,
        species: Species,
        allowed_breeds: Optional[List[str]],
        is_active: bool = True,
    ) -> Product:
        from app.modules.store.infra.db_models import ProductModel, _utcnow

        now = _utcnow()
        row = ProductModel(
            category_id=category_id,
            name=name,
            species=species.value,
            allowed_breeds=allowed_breeds or None,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_product(row)

    async def update_product(self, product_id: UUID, patch: dict) -> Product:
        from app.modules.store.infra.db_models import ProductModel, _utcnow

        row = await self._session.get(ProductModel, product_id)
        if row is None:
            raise ValueError("product_not_found")
        for key, value in patch.items():
            setattr(row, key, value)
        row.updated_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_product(row)

    async def set_product_active(self, product_id: UUID, is_active: bool) -> Product:
        from app.modules.store.infra.db_models import ProductModel, _utcnow

        row = await self._session.get(ProductModel, product_id)
        if row is None:
            raise ValueError("product_not_found")
        row.is_active = is_active
        row.updated_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_product(row)

    # ------------------------------------------------------------------
    # Addons
    # ------------------------------------------------------------------

    async def list_addons(self, *, product_id: UUID, breed: Optional[str] = None) -> List[Addon]:
        from app.modules.store.infra.db_models import AddonModel

        stmt = select(AddonModel).where(
            AddonModel.product_id == product_id,
            AddonModel.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        if breed is not None:
            rows = [r for r in rows if _breed_allowed(r.allowed_breeds, breed)]

        return [self._to_addon(r) for r in rows]

    async def get_addon(self, addon_id: UUID) -> Optional[Addon]:
        from app.modules.store.infra.db_models import AddonModel

        row = await self._session.get(AddonModel, addon_id)
        return self._to_addon(row) if row else None

    async def create_addon(
        self,
        *,
        product_id: UUID,
        name: str,
        species: Species,
        allowed_breeds: Optional[List[str]],
        is_active: bool = True,
    ) -> Addon:
        from app.modules.store.infra.db_models import AddonModel, _utcnow

        now = _utcnow()
        row = AddonModel(
            product_id=product_id,
            name=name,
            species=species.value,
            allowed_breeds=allowed_breeds or None,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_addon(row)

    async def update_addon(self, addon_id: UUID, patch: dict) -> Addon:
        from app.modules.store.infra.db_models import AddonModel, _utcnow

        row = await self._session.get(AddonModel, addon_id)
        if row is None:
            raise ValueError("addon_not_found")
        for key, value in patch.items():
            setattr(row, key, value)
        row.updated_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_addon(row)

    async def set_addon_active(self, addon_id: UUID, is_active: bool) -> Addon:
        from app.modules.store.infra.db_models import AddonModel, _utcnow

        row = await self._session.get(AddonModel, addon_id)
        if row is None:
            raise ValueError("addon_not_found")
        row.is_active = is_active
        row.updated_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_addon(row)

    # ------------------------------------------------------------------
    # Price rules
    # ------------------------------------------------------------------

    async def list_price_rules(self, *, target_id: UUID) -> List[PriceRule]:
        from app.modules.store.infra.db_models import StorePriceRuleModel

        result = await self._session.execute(
            select(StorePriceRuleModel).where(StorePriceRuleModel.target_id == target_id)
        )
        return [self._to_price_rule(r) for r in result.scalars().all()]

    async def create_price_rule(
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
        from app.modules.store.infra.db_models import StorePriceRuleModel, _utcnow

        now = _utcnow()
        row = StorePriceRuleModel(
            target_id=target_id,
            target_type=target_type,
            species=species.value,
            breed_category=breed_category,
            weight_min=weight_min,
            weight_max=weight_max,
            price=Decimal(price),
            currency=currency,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_price_rule(row)

    async def update_price_rule(self, rule_id: UUID, patch: dict) -> PriceRule:
        from app.modules.store.infra.db_models import StorePriceRuleModel, _utcnow

        row = await self._session.get(StorePriceRuleModel, rule_id)
        if row is None:
            raise ValueError("price_rule_not_found")
        for key, value in patch.items():
            if key == "price":
                row.price = Decimal(value)
            else:
                setattr(row, key, value)
        row.updated_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_price_rule(row)

    async def price_for(
        self,
        *,
        target_id: UUID,
        target_type: str,
        species: Species,
        breed_category: str,
        weight: float,
    ) -> Optional[int]:
        from app.modules.store.infra.db_models import StorePriceRuleModel

        async def _find(cat: str) -> Optional[StorePriceRuleModel]:
            stmt = (
                select(StorePriceRuleModel)
                .where(
                    and_(
                        StorePriceRuleModel.is_active.is_(True),
                        StorePriceRuleModel.target_id == target_id,
                        StorePriceRuleModel.target_type == target_type,
                        StorePriceRuleModel.species == species.value,
                        StorePriceRuleModel.breed_category == cat,
                        StorePriceRuleModel.weight_min <= weight,
                        (StorePriceRuleModel.weight_max.is_(None) | (StorePriceRuleModel.weight_max >= weight)),
                    )
                )
                .order_by(StorePriceRuleModel.weight_min.desc())
            )
            result = await self._session.execute(stmt)
            return result.scalars().first()

        rule = await _find(breed_category)
        if rule is None and breed_category != "mestizo":
            rule = await _find("mestizo")

        if rule is None:
            return None

        return int(rule.price)
