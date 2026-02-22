from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.core.auth import create_access_token, create_refresh_token, hash_password
from app.modules.iam.domain.user import UserRepository


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
