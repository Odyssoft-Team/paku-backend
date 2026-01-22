from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.modules.clinical_history.api.schemas import ClinicalEntryOut
from app.modules.clinical_history.app.use_cases import ListClinicalHistory

router = APIRouter(tags=["clinical_history"])


@router.get("/pets/{pet_id}/clinical-history", response_model=List[ClinicalEntryOut])
async def get_clinical_history(
    pet_id: UUID,
    _: CurrentUser = Depends(get_current_user),
) -> List[ClinicalEntryOut]:
    entries = ListClinicalHistory().execute(pet_id=pet_id)
    return [ClinicalEntryOut(**e.__dict__) for e in entries]
