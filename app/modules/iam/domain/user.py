from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Protocol
from uuid import UUID, uuid4

Role = Literal["admin", "user", "groomer"]


class Sex(str, Enum):
    male = "male"
    female = "female"


@dataclass(frozen=True)
class Address:
    district_id: str
    address_line: str
    lat: float
    lng: float


class DniYaRegistrado(Exception):
    """La base rechazó el DNI por el índice único (otra cuenta lo guardó a la vez). Ver PAKU-USERS-009."""


@dataclass(frozen=True)
class DatosLegales:
    """Nombres oficiales del DNI de la cuenta (feature 0027), separados del nombre visible (first_name/last_name).

    Vienen de una consulta hecha por el servidor (nunca de lo que escribe el cliente). Son datos oficiales del DNI,
    **no** una verificación de titularidad: no prueban que el usuario sea el titular de ese DNI.
    """

    nombres: str
    apellidos: str
    fuente: str
    consultado_en: datetime


@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    role: Role
    is_active: bool
    created_at: datetime
    first_name: str
    last_name: str
    # Campos opcionales — None para usuarios registrados vía social login
    password_hash: Optional[str]
    phone: Optional[str]
    sex: Optional[Sex]
    birth_date: Optional[date]
    profile_completed: bool = True
    dni: Optional[str] = None
    address: Optional[Address] = None
    profile_photo_url: Optional[str] = None
    datos_legales: Optional[DatosLegales] = None

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
        """Factory para usuarios registrados con email y contraseña."""
        return User(
            id=uuid4(),
            email=email.lower(),
            password_hash=password_hash,
            role=role,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            birth_date=birth_date,
            profile_completed=True,
            dni=dni,
            address=address,
            profile_photo_url=profile_photo_url,
        )

    @staticmethod
    def new_social(
        email: str,
        first_name: str,
        last_name: str,
        role: Role = "user",
        profile_photo_url: Optional[str] = None,
    ) -> "User":
        """Factory para usuarios registrados vía Google / Apple / Facebook.
        El perfil queda incompleto hasta que el usuario proporcione phone, sex y birth_date.
        """
        return User(
            id=uuid4(),
            email=email.lower(),
            password_hash=None,
            role=role,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            phone=None,
            first_name=first_name,
            last_name=last_name,
            sex=None,
            birth_date=None,
            profile_completed=False,
            profile_photo_url=profile_photo_url,
        )


def has_required_profile(user) -> bool:
    """Datos que se piden para reservar: teléfono, sexo y fecha de nacimiento (los que el login social no trae)."""
    return bool((getattr(user, "phone", None) or "").strip()) and getattr(user, "sex", None) is not None \
        and getattr(user, "birth_date", None) is not None


def campos_faltantes(user, *, exigir_dni: bool) -> list[str]:
    """Datos que le faltan al perfil para reservar (feature 0027). El DNI solo se exige a clientes (rol user)."""
    faltan: list[str] = []
    if not (getattr(user, "profile_completed", False) or has_required_profile(user)):
        if not (getattr(user, "phone", None) or "").strip():
            faltan.append("phone")
        if getattr(user, "sex", None) is None:
            faltan.append("sex")
        if getattr(user, "birth_date", None) is None:
            faltan.append("birth_date")
    if exigir_dni and getattr(user, "role", "user") == "user" and not getattr(user, "dni", None):
        faltan.append("dni")
    return faltan


class UserRepository(Protocol):
    async def add(self, user: User) -> None:
        ...

    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    async def get_by_dni(self, dni: str) -> Optional[User]:
        ...

    async def get_by_id(self, id: UUID) -> Optional[User]:
        ...

    async def update(self, user: User) -> None:
        ...

    async def update_password(self, user_id: UUID, new_hash: str) -> None:
        ...


class AddressRepository(Protocol):
    async def list_addresses_by_user(self, user_id: UUID, include_deleted: bool = False) -> list[Any]:
        ...

    async def get_address_for_user(self, user_id: UUID, address_id: UUID) -> Optional[Any]:
        ...

    async def create_address(self, user_id: UUID, address_data: Any) -> Any:
        ...

    async def update_address(self, user_id: UUID, address_id: UUID, patch: Any) -> Any:
        ...

    async def soft_delete_address(self, user_id: UUID, address_id: UUID) -> None:
        ...

    async def set_default_address(self, user_id: UUID, address_id: UUID) -> None:
        ...

    async def get_default_address(self, user_id: UUID) -> Optional[Any]:
        ...
