from dataclasses import dataclass
from typing import List
from uuid import UUID

from app.modules.clinical_history.domain.clinical_entry import ClinicalEntry
from app.modules.clinical_history.infra.clinical_repository import list_by_pet


@dataclass
class ListClinicalHistory:
    def execute(self, *, pet_id: UUID) -> List[ClinicalEntry]:
        return list_by_pet(pet_id)
