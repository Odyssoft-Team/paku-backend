from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

Role = Literal["admin", "user", "ally"]
Sex = Literal["male", "female"]


class AddressIn(BaseModel):
    district_id: str
    address_line: str
    lat: float
    lng: float


class AddressOut(BaseModel):
    district_id: str
    address_line: str
    lat: float
    lng: float


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
    address: Optional[AddressIn] = None
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
    phone: str
    first_name: str
    last_name: str
    sex: Sex
    birth_date: date
    dni: Optional[str] = None
    address: Optional[AddressOut] = None
    profile_photo_url: Optional[str] = None


class UpdateProfileIn(BaseModel):
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    dni: Optional[str] = None
    address: Optional[AddressIn] = None
    profile_photo_url: Optional[str] = None
