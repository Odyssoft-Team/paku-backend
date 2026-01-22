from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ClinicalEntry:
    id: UUID
    pet_id: UUID
    type: str
    summary: str
    created_at: datetime

    @staticmethod
    def new(*, pet_id: UUID, type: str, summary: str, created_at: datetime) -> "ClinicalEntry":
        return ClinicalEntry(
            id=uuid4(),
            pet_id=pet_id,
            type=type,
            summary=summary,
            created_at=created_at,
        )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
