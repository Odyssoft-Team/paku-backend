from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

Role = Literal["admin", "user", "ally"]
Sex = Literal["male", "female"]


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
    email: str
    password: str
    phone: str
    first_name: str
    last_name: str
    sex: Sex
    birth_date: date
    role: Role = "user"
    dni: Optional[str] = None
    profile_photo_url: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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


class UpdateProfileIn(BaseModel):
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    dni: Optional[str] = None
    profile_photo_url: Optional[str] = None


class AdminCreateUserIn(BaseModel):
    email: str
    password: str
    phone: str
    first_name: str
    last_name: str
    sex: Sex
    birth_date: date
    role: Role
    dni: Optional[str] = None
    profile_photo_url: Optional[str] = None


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
    dni: Optional[str] = None
