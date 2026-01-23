from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class PetWeightEntry:
    id: UUID
    pet_id: UUID
    weight_kg: float
    recorded_at: datetime

    @staticmethod
    def new(*, pet_id: UUID, weight_kg: float) -> "PetWeightEntry":
        return PetWeightEntry(
            id=uuid4(),
            pet_id=pet_id,
            weight_kg=weight_kg,
            recorded_at=datetime.now(timezone.utc),
        )
