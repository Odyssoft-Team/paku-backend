from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

# [TECH]
# Type alias for user roles accepted by the API layer.
# Used by DTOs to validate incoming/outgoing payloads (register/profile).
# Participates in authorization indirectly because the role claim is embedded into tokens.
#
# [BUSINESS]
# Define los tipos de roles que un usuario puede tener en la plataforma.
# Esto permite distinguir perfiles (por ejemplo usuario final vs administrador) y aplicar
# reglas de acceso de forma consistente.
Role = Literal["admin", "user", "ally"]

# [TECH]
# Type alias for sex values accepted by the API layer.
# Used only for validation/serialization in IAM user profile payloads.
#
# [BUSINESS]
# Define los valores permitidos para el campo de sexo en el perfil del usuario.
# Ayuda a mantener datos consistentes.
Sex = Literal["male", "female"]


# [TECH]
# Output DTO for district data.
# Used to serialize district information for API responses.
#
# [BUSINESS]
# Representación de distrito para consultas geográficas.
class DistrictOut(BaseModel):
    id: str
    name: str
    province_name: Optional[str] = None
    department_name: Optional[str] = None
    active: bool


# [TECH]
# Input DTO for creating user addresses.
# Used to validate address creation requests.
#
# [BUSINESS]
# Datos necesarios para crear una nueva dirección en la libreta del usuario.
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


# [TECH]
# Input DTO for updating user addresses.
# All fields are optional to allow partial updates.
#
# [BUSINESS]
# Datos que el usuario puede modificar de una dirección existente.
class AddressUpdateIn(BaseModel):
    district_id: Optional[str] = None
    address_line: Optional[str] = None
    reference: Optional[str] = None
    building_number: Optional[str] = None
    apartment_number: Optional[str] = None
    label: Optional[str] = None
    type: Optional[str] = None
    is_default: Optional[bool] = None


# [TECH]
# Output DTO for user addresses with full details.
# Used to serialize address data for API responses.
#
# [BUSINESS]
# Representación completa de dirección para respuestas de la API.
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


# [TECH]
# Input DTO for user registration.
# Receives credentials (email/password) and personal profile data.
# Output: validated payload passed to the RegisterUser use case.
# Flow: authentication (account creation).
#
# [BUSINESS]
# Datos necesarios para crear una cuenta.
# Incluye correo y contraseña, además de información personal básica del usuario.
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


# [TECH]
# Input DTO for login.
# Receives email/password to authenticate and request tokens.
# Flow: authentication (login).
#
# [BUSINESS]
# Datos mínimos para iniciar sesión: correo y contraseña.
class LoginIn(BaseModel):
    email: str
    password: str


# [TECH]
# Input DTO for refreshing an access token.
# Receives refresh_token previously issued during login.
# Flow: authentication (token renewal).
#
# [BUSINESS]
# Token de renovación de sesión.
# Permite continuar usando la app sin volver a ingresar contraseña.
class RefreshIn(BaseModel):
    refresh_token: str


# [TECH]
# Output DTO for token responses.
# Contains access_token and refresh_token.
# Flow: returned by login and refresh endpoints.
#
# [BUSINESS]
# Respuesta de autenticación: contiene los tokens que la app usará para
# mantener la sesión del usuario.
class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# [TECH]
# Output DTO for user profile.
# Serializes the domain User entity to API consumers.
# Flow: returned after register and in /users/me GET/PUT.
#
# [BUSINESS]
# Representa el perfil del usuario tal como lo ve la app.
# Incluye datos personales y el estado de la cuenta.
class UserOut(BaseModel):
    id: UUID
    email: str
    role: Role
    is_active: bool
    created_at: datetime
    phone: str
    first_name: str
    last_name: str
    sex: Sex
    birth_date: date
    dni: Optional[str] = None
    profile_photo_url: Optional[str] = None


# [TECH]
# Input DTO for updating the current user's profile.
# All fields are optional; only provided fields should be updated.
# Flow: profile management (/users/me PUT).
#
# [BUSINESS]
# Datos que el usuario puede editar en su perfil.
# Se envían solo los campos que se desean cambiar.
class UpdateProfileIn(BaseModel):
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    dni: Optional[str] = None
    profile_photo_url: Optional[str] = None
