from datetime import timedelta
from typing import List
from uuid import UUID

from app.modules.clinical_history.domain.clinical_entry import ClinicalEntry, utcnow


def list_by_pet(pet_id: UUID) -> List[ClinicalEntry]:
    now = utcnow()
    entries = [
        ClinicalEntry.new(
            pet_id=pet_id,
            type="note",
            summary="Entrada placeholder: nota clinica.",
            created_at=now,
        ),
        ClinicalEntry.new(
            pet_id=pet_id,
            type="vaccine",
            summary="Entrada placeholder: vacuna registrada.",
            created_at=now - timedelta(days=7),
        ),
    ]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries
