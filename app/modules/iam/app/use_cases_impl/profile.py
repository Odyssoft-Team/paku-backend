from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.auth import hash_password
from app.modules.iam.domain.user import Address, Role, Sex, User, UserRepository


@dataclass
class RegisterUser:
    repo: UserRepository

    async def execute(
        self,
        email: str,
        password: str,
        phone: str,
        first_name: str,
        last_name: str,
        sex: Sex,
        birth_date: date,
        role: Role = "user",
        dni: Optional[str] = None,
        address: Optional[Address] = None,
        profile_photo_url: Optional[str] = None,
    ) -> User:
        existing = await self.repo.get_by_email(email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user = User.new(
            email=email,
            password_hash=hash_password(password),
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            birth_date=birth_date,
            role=role,
            dni=dni,
            address=address,
            profile_photo_url=profile_photo_url,
        )
        await self.repo.add(user)
        return user


@dataclass
class GetMe:
    repo: UserRepository

    async def execute(self, user_id: UUID) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user


@dataclass
class UpdateProfile:
    repo: UserRepository

    async def execute(
        self,
        user_id: UUID,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        sex: Optional[Sex] = None,
        birth_date: Optional[date] = None,
        dni: Optional[str] = None,
        address: Optional[Address] = None,
        profile_photo_url: Optional[str] = None,
    ) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        updated = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            phone=phone if phone is not None else user.phone,
            first_name=first_name if first_name is not None else user.first_name,
            last_name=last_name if last_name is not None else user.last_name,
            sex=sex if sex is not None else user.sex,
            birth_date=birth_date if birth_date is not None else user.birth_date,
            profile_completed=user.profile_completed,  # preservar siempre
            dni=dni if dni is not None else user.dni,
            address=address if address is not None else user.address,
            profile_photo_url=profile_photo_url if profile_photo_url is not None else user.profile_photo_url,
        )
        await self.repo.update(updated)
        return updated


@dataclass
class ChangeUserRole:
    """Cambia el rol de un usuario. Solo ejecutable por admins."""

    repo: UserRepository

    async def execute(self, user_id: UUID, role: Role) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        updated = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=role,
            is_active=user.is_active,
            created_at=user.created_at,
            phone=user.phone,
            first_name=user.first_name,
            last_name=user.last_name,
            sex=user.sex,
            birth_date=user.birth_date,
            profile_completed=user.profile_completed,
            dni=user.dni,
            address=user.address,
            profile_photo_url=user.profile_photo_url,
        )
        await self.repo.update(updated)
        return updated


@dataclass
class CompleteProfile:
    """Completa el perfil de un usuario social (Google/Apple/Facebook).
    Recibe los campos obligatorios que el proveedor no entregó y marca profile_completed=True.
    """
    repo: UserRepository

    async def execute(
        self,
        user_id: UUID,
        phone: str,
        sex: Sex,
        birth_date: date,
        dni: Optional[str] = None,
    ) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        updated = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_photo_url=user.profile_photo_url,
            phone=phone,
            sex=sex,
            birth_date=birth_date,
            profile_completed=True,
            dni=dni if dni is not None else user.dni,
            address=user.address,
        )
        await self.repo.update(updated)
        return updated
