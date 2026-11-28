from datetime import date, datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

import re
from pydantic import BaseModel, BeforeValidator, EmailStr, field_validator

from app.modules.iam.domain.dni import normalizar_dni

Role = Literal["admin", "user", "groomer"]
Sex = Literal["male", "female"]
# DNI de 8 dígitos; vacío = no enviado (feature 0027). 422 si el formato no es válido.
Dni = Annotated[Optional[str], BeforeValidator(normalizar_dni)]


class AddressCreateIn(BaseModel):
    district_id: str
    address_line: str
    lat: float
    lng: float
    reference: Optional[str] = None
    building_number: Optional[str] = None
    apartment_number: Optional[str] = None
    label: Optional[str] = None
    type: Optional[str] = None
    is_default: Optional[bool] = False


class AddressUpdateIn(BaseModel):
    district_id: Optional[str] = None
    address_line: Optional[str] = None
    reference: Optional[str] = None
    building_number: Optional[str] = None
    apartment_number: Optional[str] = None
    label: Optional[str] = None
    type: Optional[str] = None
    is_default: Optional[bool] = None


class AddressOutExtended(BaseModel):
    id: UUID
    district_id: str
    address_line: str
    lat: float
    lng: float
    reference: Optional[str] = None
    building_number: Optional[str] = None
    apartment_number: Optional[str] = None
    label: Optional[str] = None
    type: Optional[str] = None
    is_default: bool
    created_at: datetime


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    phone: str
    first_name: str
    last_name: str
    sex: Sex
    birth_date: date
    dni: Dni = None
    # role es siempre "user" en registro público — no se acepta del cliente
    # profile_photo_url se gestiona exclusivamente a través del módulo media (POST /media/confirm-profile-photo)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        if not re.fullmatch(r"\+?[0-9]{7,15}", v.strip()):
            raise ValueError("Formato de teléfono inválido")
        return v.strip()


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserSearchResultOut(BaseModel):
    """Resultado liviano para el combobox de búsqueda de admin (GET /admin/users/search)."""
    id: UUID
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: str


class UserOut(BaseModel):
    id: UUID
    email: str
    role: Role
    is_active: bool
    created_at: datetime
    first_name: str
    last_name: str
    profile_completed: bool = True
    # Opcionales — None para usuarios sociales con perfil incompleto
    phone: Optional[str] = None
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    dni: Optional[str] = None
    profile_photo_url: Optional[str] = None
    # Lo que falta para reservar (feature 0027): p. ej. ["dni"] para regularizar a un cliente existente.
    missing_profile_fields: list[str] = []
    # Nombres oficiales del DNI (feature 0027), separados del nombre visible (first_name/last_name). Los llena el
    # servidor con una consulta a Datos Perú; el cliente no puede enviarlos. NO es verificación de titularidad.
    legal_first_name: Optional[str] = None
    legal_last_name: Optional[str] = None
    legal_data_source: Optional[str] = None
    legal_data_checked_at: Optional[datetime] = None


class UpdateProfileIn(BaseModel):
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    dni: Dni = None
    # profile_photo_url se gestiona exclusivamente a través del módulo media (POST /media/confirm-profile-photo)


class AdminCreateUserIn(BaseModel):
    email: EmailStr
    password: str
    phone: str
    first_name: str
    last_name: str
    sex: Sex
    birth_date: date
    role: Role
    dni: Dni = None
    # profile_photo_url se gestiona exclusivamente a través del módulo media (POST /media/confirm-profile-photo)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        if not re.fullmatch(r"\+?[0-9]{7,15}", v.strip()):
            raise ValueError("Formato de teléfono inválido")
        return v.strip()


# ------------------------------------------------------------------
# Social login
# ------------------------------------------------------------------

class SocialLoginIn(BaseModel):
    """ID Token emitido por Firebase en el dispositivo móvil."""
    id_token: str


class SocialTokenOut(BaseModel):
    """Respuesta de autenticación social. is_new_user=True indica que el perfil está incompleto."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool


class CompleteProfileIn(BaseModel):
    """Datos requeridos para completar el perfil de un usuario social."""
    phone: str
    sex: Sex
    birth_date: date
    dni: Dni = None


# ------------------------------------------------------------------
# Account linking
# ------------------------------------------------------------------

class ChangeRoleIn(BaseModel):
    """Cambia el rol de un usuario (solo admin)."""
    role: Role


class SetPasswordIn(BaseModel):
    """Agrega o cambia la contraseña del usuario autenticado.
    - Sin contraseña previa (cuenta social): solo new_password.
    - Con contraseña previa: también current_password.
    """
    new_password: str
    current_password: Optional[str] = None

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v


class LinkSocialIn(BaseModel):
    """Vincula una identidad social (Firebase) a la cuenta actual."""
    id_token: str


class LinkedIdentityOut(BaseModel):
    """Identidad social vinculada."""
    id: UUID
    provider: str
    created_at: datetime


class DniConsultaIn(BaseModel):
    """DNI a consultar para autocompletar nombres y apellidos (feature 0027)."""

    dni: Dni

    @field_validator("dni")
    @classmethod
    def _obligatorio(cls, v: Optional[str]) -> str:
        if v is None:
            raise ValueError("Indique el DNI.")
        return v


class DniConsultaOut(BaseModel):
    """Solo nombres y apellidos: la consulta no devuelve otros datos de la persona."""

    dni: str
    nombres: str
    apellidos: str
