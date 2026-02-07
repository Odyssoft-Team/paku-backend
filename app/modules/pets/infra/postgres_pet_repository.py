from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.pets.domain.pet import Pet, PetRepository, Sex, Species
from app.modules.pets.domain.weight_entry import PetWeightEntry


class PostgresPetRepository(PetRepository):
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def add(self, pet: Pet) -> None:
        from app.modules.pets.infra.models import PetModel, ensure_pets_schema, utcnow

        await ensure_pets_schema(self._engine)

        model = PetModel(
            id=pet.id,
            owner_id=pet.owner_id,
            name=pet.name,
            species=str(pet.species.value if hasattr(pet.species, "value") else pet.species),
            breed=pet.breed,
            sex=(str(pet.sex.value) if pet.sex is not None else None),
            birth_date=pet.birth_date,
            notes=pet.notes,
            photo_url=pet.photo_url,
            weight_kg=pet.weight_kg,
            created_at=pet.created_at,
            updated_at=utcnow(),
        )
        self._session.add(model)
        await self._session.commit()

    async def get_by_id(self, pet_id: UUID) -> Optional[Pet]:
        from app.modules.pets.infra.models import PetModel, ensure_pets_schema

        await ensure_pets_schema(self._engine)

        model = await self._session.get(PetModel, pet_id)
        if model is None:
            return None

        sex = None
        if model.sex is not None:
            sex = Sex(model.sex)

        species = Species(model.species)

        return Pet(
            id=model.id,
            owner_id=model.owner_id,
            name=model.name,
            species=species,
            breed=model.breed,
            sex=sex,
            birth_date=model.birth_date,
            notes=model.notes,
            created_at=model.created_at,
            photo_url=model.photo_url,
            weight_kg=model.weight_kg,
            updated_at=model.updated_at,
        )

    async def update(self, pet: Pet) -> None:
        from app.modules.pets.infra.models import PetModel, ensure_pets_schema, utcnow

        await ensure_pets_schema(self._engine)

        model = await self._session.get(PetModel, pet.id)
        if model is None:
            raise ValueError("pet_not_found")

        model.name = pet.name
        model.species = str(pet.species.value if hasattr(pet.species, "value") else pet.species)
        model.breed = pet.breed
        model.sex = (str(pet.sex.value) if pet.sex is not None else None)
        model.birth_date = pet.birth_date
        model.notes = pet.notes
        model.photo_url = pet.photo_url
        model.weight_kg = pet.weight_kg
        model.updated_at = utcnow()

        await self._session.commit()

    async def add_weight_entry(self, entry: PetWeightEntry) -> None:
        """ from app.modules.pets.infra.models import PetWeightEntryModel, ensure_pets_schema, utcnow """
        from app.modules.pets.infra.models import PetWeightEntryModel, ensure_pets_schema

        await ensure_pets_schema(self._engine)

        model = PetWeightEntryModel(
            id=entry.id,
            pet_id=entry.pet_id,
            weight_kg=entry.weight_kg,
            recorded_at=entry.recorded_at,
        )
        self._session.add(model)
        await self._session.commit()

    async def get_weight_history(self, pet_id: UUID) -> List[PetWeightEntry]:
        from app.modules.pets.infra.models import PetWeightEntryModel, ensure_pets_schema

        await ensure_pets_schema(self._engine)

        stmt = (
            select(PetWeightEntryModel)
            .where(PetWeightEntryModel.pet_id == pet_id)
            .order_by(desc(PetWeightEntryModel.recorded_at))
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [
            PetWeightEntry(
                id=model.id,
                pet_id=model.pet_id,
                weight_kg=model.weight_kg,
                recorded_at=model.recorded_at,
            )
            for model in models
        ]

    async def list_by_owner(self, owner_id: UUID, limit: int = 7, offset: int = 0) -> List[Pet]:
        from app.modules.pets.infra.models import PetModel, ensure_pets_schema

        await ensure_pets_schema(self._engine)

        # Apply limits: max 14, default 7
        limit = min(max(limit, 1), 14)
        offset = max(offset, 0)

        stmt = (
            select(PetModel)
            .where(PetModel.owner_id == owner_id)
            .order_by(desc(PetModel.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [
            Pet(
                id=model.id,
                owner_id=model.owner_id,
                name=model.name,
                species=Species(model.species),
                breed=model.breed,
                sex=(Sex(model.sex) if model.sex is not None else None),
                birth_date=model.birth_date,
                notes=model.notes,
                created_at=model.created_at,
                photo_url=model.photo_url,
                weight_kg=model.weight_kg,
                updated_at=model.updated_at,
            )
            for model in models
        ]
