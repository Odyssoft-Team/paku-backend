from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class SocialIdentity:
    """Vincula una cuenta local de Paku con una identidad de Firebase (Google/Apple/Facebook)."""
    id: UUID
    user_id: UUID
    provider: str       # "google.com" | "apple.com" | "facebook.com"
    firebase_uid: str   # uid del token de Firebase — fuente de verdad de identidad
    created_at: datetime

    @staticmethod
    def new(user_id: UUID, provider: str, firebase_uid: str) -> "SocialIdentity":
        return SocialIdentity(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            firebase_uid=firebase_uid,
            created_at=datetime.now(timezone.utc),
        )


class SocialIdentityRepository(Protocol):
    async def get_by_firebase_uid(self, firebase_uid: str) -> Optional[SocialIdentity]:
        ...

    async def add(self, identity: SocialIdentity) -> None:
        ...
