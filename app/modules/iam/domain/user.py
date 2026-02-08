from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Protocol
from uuid import UUID, uuid4

# [TECH]
# Type alias representing the set of roles supported by the IAM domain.
# This is the authoritative role set used by the User entity and propagated into tokens.
# It participates in authorization because downstream modules may rely on the role claim.
#
# [BUSINESS]
# Define los perfiles/roles disponibles para usuarios.
# Esto permite clasificar a los usuarios (por ejemplo usuario final, aliado o administrador)
# y aplicar reglas de acceso según el rol.
Role = Literal["admin", "user", "ally"]


# [TECH]
# Enum representing the user's sex in the domain.
# Used by the User entity and validated/serialized through the API layer.
#
# [BUSINESS]
# Valores permitidos para el sexo del usuario en su perfil.
# Sirve para mantener información consistente.
class Sex(str, Enum):
    male = "male"
    female = "female"


@dataclass(frozen=True)
# [TECH]
# Domain value object representing an address.
# Used as part of the User entity.
# Inputs: district_id, address_line, coordinates.
#
# [BUSINESS]
# Dirección del usuario (zona y referencia).
# Ayuda a ubicar al usuario para operaciones y prestación de servicios.
class Address:
    district_id: str
    address_line: str
    lat: float
    lng: float


@dataclass(frozen=True)
# [TECH]
# Core domain entity representing a platform user.
# Contains identity (id/email), authentication material (password_hash), authorization (role),
# account state (is_active) and profile information.
# Flow: used across IAM registration, login, token minting, and profile management.
#
# [BUSINESS]
# Representa a una persona/cliente dentro del sistema.
# Incluye su correo, estado de cuenta y datos del perfil que la app muestra y actualiza.
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
    # [TECH]
    # Factory method to create a new User with normalized email and generated UUID.
    # Inputs: email, password_hash (already hashed), profile fields, role, and optional extras.
    # Output: a fully populated User domain object.
    # Flow: registration. Called by RegisterUser use case before persistence.
    #
    # [BUSINESS]
    # Crea un usuario nuevo con un identificador único y el correo normalizado.
    # Se usa cuando alguien se registra por primera vez.
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
            dni=dni,
            address=address,
            profile_photo_url=profile_photo_url,
        )


# [TECH]
# Repository interface for persistence of User entities.
# Defines the required operations for IAM use cases (lookup by email/id, add, update).
# Implementations can be in-memory or database-backed.
#
# [BUSINESS]
# Contrato de almacenamiento de usuarios.
# Permite buscar, crear y actualizar usuarios sin depender de una tecnología específica.
class UserRepository(Protocol):
    async def add(self, user: User) -> None:
        ...

    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    async def get_by_id(self, id: UUID) -> Optional[User]:
        ...

    async def update(self, user: User) -> None:
        ...


# [TECH]
# Protocol defining repository operations for user address management.
# Implemented by infrastructure layer (PostgresAddressRepository).
#
# [BUSINESS]
# Interfaz para gestionar libreta de direcciones del usuario.
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
