from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional, Protocol
from uuid import UUID, uuid4

Role = Literal["admin", "user", "ally"]


@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    password_hash: str
    role: Role
    is_active: bool
    created_at: datetime

    @staticmethod
    def new(email: str, password_hash: str, role: Role = "user") -> "User":
        return User(
            id=uuid4(),
            email=email.strip().lower(),
            password_hash=password_hash,
            role=role,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    async def add(self, user: User) -> None:
        ...
