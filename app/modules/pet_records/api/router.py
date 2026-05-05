from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.pet_records.api.schemas import PetRecordCreateIn, PetRecordOut
from app.modules.pet_records.app.use_cases import CreateRecord, DeleteRecord, GetRecord, ListRecords
from app.modules.pet_records.domain.record import RecordRole, RecordType
from app.modules.pet_records.infra.postgres_pet_records_repository import PostgresPetRecordsRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository

router = APIRouter(tags=["pet_records"])


def get_records_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresPetRecordsRepository:
    return PostgresPetRecordsRepository(session=session)


def get_pet_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresPetRepository:
    return PostgresPetRepository(session=session, engine=engine)


# ---------------------------------------------------------------------------
# POST /pets/{pet_id}/records
# ---------------------------------------------------------------------------

@router.post(
    "/pets/{pet_id}/records",
    response_model=PetRecordOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_record(
    pet_id: UUID,
    payload: PetRecordCreateIn,
    current: CurrentUser = Depends(get_current_user),
    records_repo: PostgresPetRecordsRepository = Depends(get_records_repo),
    pets_repo: PostgresPetRepository = Depends(get_pet_repo),
) -> PetRecordOut:
    record = await CreateRecord(
        records_repo=records_repo,
        pets_repo=pets_repo,
    ).execute(
        pet_id=pet_id,
        user_id=current.id,
        role=getattr(current, "role", "owner"),
        type=payload.type,
        occurred_at=payload.occurred_at,
        data=payload.data,
        title=payload.title,
        attachment_ids=payload.attachment_ids,
    )
    return PetRecordOut(**record.__dict__)


# ---------------------------------------------------------------------------
# GET /pets/{pet_id}/records
# ---------------------------------------------------------------------------

@router.get(
    "/pets/{pet_id}/records",
    response_model=list[PetRecordOut],
)
async def list_records(
    pet_id: UUID,
    type: Optional[RecordType] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    recorded_by_role: Optional[RecordRole] = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current: CurrentUser = Depends(get_current_user),
    records_repo: PostgresPetRecordsRepository = Depends(get_records_repo),
    pets_repo: PostgresPetRepository = Depends(get_pet_repo),
) -> list[PetRecordOut]:
    records = await ListRecords(
        records_repo=records_repo,
        pets_repo=pets_repo,
    ).execute(
        pet_id=pet_id,
        user_id=current.id,
        role=getattr(current, "role", "owner"),
        type=type,
        date_from=date_from,
        date_to=date_to,
        recorded_by_role=recorded_by_role,
        limit=limit,
        offset=offset,
    )
    return [PetRecordOut(**r.__dict__) for r in records]


# ---------------------------------------------------------------------------
# GET /pets/{pet_id}/records/{record_id}
# ---------------------------------------------------------------------------

@router.get(
    "/pets/{pet_id}/records/{record_id}",
    response_model=PetRecordOut,
)
async def get_record(
    pet_id: UUID,
    record_id: UUID,
    current: CurrentUser = Depends(get_current_user),
    records_repo: PostgresPetRecordsRepository = Depends(get_records_repo),
    pets_repo: PostgresPetRepository = Depends(get_pet_repo),
) -> PetRecordOut:
    record = await GetRecord(
        records_repo=records_repo,
        pets_repo=pets_repo,
    ).execute(
        pet_id=pet_id,
        record_id=record_id,
        user_id=current.id,
        role=getattr(current, "role", "owner"),
    )
    return PetRecordOut(**record.__dict__)


# ---------------------------------------------------------------------------
# DELETE /pets/{pet_id}/records/{record_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/pets/{pet_id}/records/{record_id}",
    response_model=PetRecordOut,
)
async def delete_record(
    pet_id: UUID,
    record_id: UUID,
    current: CurrentUser = Depends(get_current_user),
    records_repo: PostgresPetRecordsRepository = Depends(get_records_repo),
    pets_repo: PostgresPetRepository = Depends(get_pet_repo),
) -> PetRecordOut:
    record = await DeleteRecord(
        records_repo=records_repo,
        pets_repo=pets_repo,
    ).execute(
        pet_id=pet_id,
        record_id=record_id,
        user_id=current.id,
        role=getattr(current, "role", "owner"),
    )
    return PetRecordOut(**record.__dict__)
