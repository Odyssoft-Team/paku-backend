from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pet_records.domain.record import PetRecord, RecordRole, RecordType


class PostgresPetRecordsRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Private mapping helpers
    # ------------------------------------------------------------------

    def _to_model(self, record: PetRecord):
        from app.modules.pet_records.infra.models import PetRecordModel

        return PetRecordModel(
            id=record.id,
            pet_id=record.pet_id,
            type=record.type.value,
            title=record.title,
            occurred_at=record.occurred_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
            recorded_by_user_id=record.recorded_by_user_id,
            recorded_by_role=record.recorded_by_role.value,
            data=record.data,
            attachment_ids=[str(a) for a in record.attachment_ids],
            deleted_at=record.deleted_at,
        )

    def _to_domain(self, model) -> PetRecord:
        return PetRecord(
            id=model.id,
            pet_id=model.pet_id,
            type=RecordType(model.type),
            title=model.title,
            occurred_at=model.occurred_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            recorded_by_user_id=model.recorded_by_user_id,
            recorded_by_role=RecordRole(model.recorded_by_role),
            data=model.data or {},
            attachment_ids=[UUID(a) for a in (model.attachment_ids or [])],
            deleted_at=model.deleted_at,
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def create(self, record: PetRecord) -> PetRecord:
        model = self._to_model(record)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def get_by_id(self, record_id: UUID) -> Optional[PetRecord]:
        from app.modules.pet_records.infra.models import PetRecordModel

        model = await self._session.get(PetRecordModel, record_id)
        if model is None:
            return None
        return self._to_domain(model)

    async def list_by_pet(
        self,
        *,
        pet_id: UUID,
        type: Optional[RecordType] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        role: Optional[RecordRole] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[PetRecord]:
        from app.modules.pet_records.infra.models import PetRecordModel

        stmt = (
            select(PetRecordModel)
            .where(
                PetRecordModel.pet_id == pet_id,
                PetRecordModel.deleted_at.is_(None),
            )
        )

        if type is not None:
            stmt = stmt.where(PetRecordModel.type == type.value)
        if date_from is not None:
            stmt = stmt.where(PetRecordModel.occurred_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(PetRecordModel.occurred_at <= date_to)
        if role is not None:
            stmt = stmt.where(PetRecordModel.recorded_by_role == role.value)

        stmt = stmt.order_by(PetRecordModel.occurred_at.desc()).limit(limit).offset(offset)

        res = await self._session.execute(stmt)
        return [self._to_domain(row) for row in res.scalars().all()]

    async def soft_delete(self, record_id: UUID, deleted_at: datetime) -> Optional[PetRecord]:
        from app.modules.pet_records.infra.models import PetRecordModel

        model = await self._session.get(PetRecordModel, record_id)
        if model is None:
            return None

        if model.deleted_at is not None:
            return self._to_domain(model)

        model.deleted_at = deleted_at
        model.updated_at = deleted_at
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_domain(model)
