from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal, Optional, Protocol
from uuid import UUID, uuid4

Role = Literal["admin", "user", "ally"]


class Sex(str, Enum):
    male = "male"
    female = "female"


@dataclass(frozen=True)
class Address:
    district_id: str
    address_line: str
    lat: float
    lng: float


@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    password_hash: str
    role: Role
    is_active: bool
    created_at: datetime
    phone: str
    first_name: str
    last_name: str
    sex: Sex
    birth_date: date
    dni: Optional[str] = None
    address: Optional[Address] = None
    profile_photo_url: Optional[str] = None

    @staticmethod
    def new(
        email: str,
        password_hash: str,
        phone: str,
        first_name: str,
        last_name: str,
        sex: Sex,
        birth_date: date,
        role: Role = "user",
        dni: Optional[str] = None,
        address: Optional[Address] = None,
        profile_photo_url: Optional[str] = None,
    ) -> "User":
        return User(
            id=uuid4(),
            email=email.strip().lower(),
            password_hash=password_hash,
            role=role,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            birth_date=birth_date,
            dni=dni,
            address=address,
            profile_photo_url=profile_photo_url,
        )


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    async def add(self, user: User) -> None:
        ...

    async def update(self, user: User) -> None:
        ...
