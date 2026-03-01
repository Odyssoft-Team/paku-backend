from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.catalog.domain.breed import Breed
from app.modules.catalog.infra.models import BreedModel

_catalog_seeded = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PostgresBreedRepository:
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    # ------------------------------------------------------------------
    # Seed idempotente — igual patrón que commerce
    # ------------------------------------------------------------------

    async def seed_if_empty(self) -> None:
        global _catalog_seeded
        if _catalog_seeded:
            return

        from app.modules.catalog.domain.breeds_data import BREEDS_CATALOG

        now = _utcnow()
        rows: list[BreedModel] = []
        for group in BREEDS_CATALOG:
            species = group["species"]
            for b in group["breeds"]:
                rows.append(
                    BreedModel(
                        id=b["id"],
                        name=b["name"],
                        species=species,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )

        for row in rows:
            try:
                self._session.add(row)
                await self._session.flush()
            except IntegrityError:
                await self._session.rollback()

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()

        _catalog_seeded = True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def _to_domain(self, m: BreedModel) -> Breed:
        return Breed(id=m.id, name=m.name, species=m.species, is_active=m.is_active)

    async def list_active(self, *, species: Optional[str] = None) -> list[Breed]:
        await self.seed_if_empty()
        stmt = select(BreedModel).where(BreedModel.is_active.is_(True))
        if species:
            stmt = stmt.where(BreedModel.species == species.strip().lower())
        stmt = stmt.order_by(BreedModel.species, BreedModel.name)
        res = await self._session.execute(stmt)
        return [self._to_domain(r) for r in res.scalars().all()]

    async def list_all(self, *, species: Optional[str] = None) -> list[Breed]:
        """Admin: devuelve todas incluidas las inactivas."""
        await self.seed_if_empty()
        stmt = select(BreedModel)
        if species:
            stmt = stmt.where(BreedModel.species == species.strip().lower())
        stmt = stmt.order_by(BreedModel.species, BreedModel.name)
        res = await self._session.execute(stmt)
        return [self._to_domain(r) for r in res.scalars().all()]

    async def get(self, breed_id: str) -> Optional[Breed]:
        await self.seed_if_empty()
        m = await self._session.get(BreedModel, breed_id)
        return self._to_domain(m) if m else None

    async def create(self, *, id: str, name: str, species: str) -> Breed:
        await self.seed_if_empty()
        now = _utcnow()
        m = BreedModel(id=id, name=name, species=species, is_active=True,
                       created_at=now, updated_at=now)
        self._session.add(m)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ValueError("breed_already_exists")
        await self._session.refresh(m)
        return self._to_domain(m)

    async def update(self, breed_id: str, patch: dict) -> Breed:
        await self.seed_if_empty()
        m = await self._session.get(BreedModel, breed_id)
        if m is None:
            raise ValueError("breed_not_found")
        for key, value in patch.items():
            setattr(m, key, value)
        m.updated_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(m)
        return self._to_domain(m)

    async def set_active(self, breed_id: str, is_active: bool) -> Breed:
        return await self.update(breed_id, {"is_active": is_active})
