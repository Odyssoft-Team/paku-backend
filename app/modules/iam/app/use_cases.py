from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.auth import create_access_token, create_refresh_token, hash_password
from app.modules.iam.domain.user import Address, Role, Sex, User, UserRepository


@dataclass
# [TECH]
# Use case responsible for creating a new user account.
# Inputs: email/password plus profile fields (phone, names, sex, birth_date, role, optional dni/address/photo).
# Output: a domain User entity persisted in the repository.
# Flow: authentication (registration). Validates uniqueness of email, hashes password,
# and delegates persistence to UserRepository.
# Depends on: UserRepository (get_by_email/add) + hash_password + User.new.
#
# [BUSINESS]
# Caso de uso que crea una cuenta nueva.
# Verifica que el correo no esté en uso, guarda la contraseña de forma segura
# y registra el perfil básico del usuario para que pueda usar la plataforma.
class RegisterUser:
    repo: UserRepository

    async def execute(
        # [TECH]
        # Orchestrates the registration flow.
        # Receives raw inputs from the API handler, validates email uniqueness,
        # hashes the password, builds the domain User, and stores it.
        # Returns the created User for serialization.
        #
        # [BUSINESS]
        # Ejecuta el registro: comprueba que el correo sea único y crea el usuario.
        # Devuelve el usuario creado para mostrarlo en la app.
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
# [TECH]
# Use case responsible for authenticating a user and issuing JWTs.
# Inputs: email, password.
# Output: dict containing access_token, refresh_token, token_type.
# Flow: authentication (login). Validates credentials, checks active status,
# and mints tokens using core auth utilities.
# Depends on: UserRepository.get_by_email + hash_password + create_access_token/create_refresh_token.
#
# [BUSINESS]
# Caso de uso para iniciar sesión.
# Valida correo y contraseña y, si son correctos, entrega tokens para que
# la app pueda mantener la sesión del usuario.
class LoginUser:
    repo: UserRepository

    async def execute(self, email: str, password: str) -> dict:
        # [TECH]
        # Validates user credentials and returns token payload.
        # If credentials are invalid returns 401; if user is inactive returns 403.
        # Part of authentication flow.
        #
        # [BUSINESS]
        # Verifica si el usuario puede ingresar.
        # Si el correo/contraseña no coinciden, rechaza el acceso.
        # Si la cuenta está inactiva, impide el inicio de sesión.
        user = await self.repo.get_by_email(email)
        if not user or user.password_hash != hash_password(password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )
        return {
            "access_token": create_access_token(user),
            "refresh_token": create_refresh_token(user),
            "token_type": "bearer",
        }


@dataclass
# [TECH]
# Use case responsible for retrieving the current user's profile.
# Inputs: user_id.
# Output: domain User.
# Flow: identity/profile read, typically called after token validation.
# Depends on: UserRepository.get_by_id.
#
# [BUSINESS]
# Caso de uso que obtiene el perfil del usuario.
# Se usa para mostrar la información del usuario autenticado.
class GetMe:
    repo: UserRepository

    async def execute(self, user_id: UUID) -> User:
        # [TECH]
        # Loads the user by ID or returns 404.
        # Part of the authenticated profile flow.
        #
        # [BUSINESS]
        # Busca al usuario por su identificador.
        # Si no existe, indica que el perfil no se encuentra.
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user


@dataclass
# [TECH]
# Use case responsible for updating the current user's profile.
# Inputs: user_id and optional profile fields.
# Output: updated domain User.
# Flow: identity/profile update. Loads existing user, merges fields, persists.
# Depends on: UserRepository.get_by_id + UserRepository.update.
#
# [BUSINESS]
# Caso de uso que permite editar el perfil del usuario.
# Solo cambia los campos enviados y mantiene el resto como estaban.
class UpdateProfile:
    repo: UserRepository

    async def execute(
        # [TECH]
        # Applies a partial update over the existing user record.
        # Receives optional fields; when a field is None it keeps the previous value.
        # Returns 404 if the user does not exist.
        #
        # [BUSINESS]
        # Actualiza el perfil del usuario con los cambios que llegan.
        # No borra información: si un campo no viene, se conserva.
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
            dni=dni if dni is not None else user.dni,
            address=address if address is not None else user.address,
            profile_photo_url=profile_photo_url if profile_photo_url is not None else user.profile_photo_url,
        )
        await self.repo.update(updated)
        return updated
