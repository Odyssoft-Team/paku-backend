from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.core.auth import hash_password
from app.modules.iam.domain.oauth_provider import OAuthProvider
from app.modules.iam.domain.social_identity import SocialIdentity, SocialIdentityRepository
from app.modules.iam.domain.user import User, UserRepository


@dataclass
class AddPassword:
    """Agrega o cambia la contraseña de un usuario.

    - Usuario sin contraseña (social): solo recibe la nueva contraseña.
    - Usuario con contraseña: debe proporcionar la contraseña actual para cambiarla.
    """

    repo: UserRepository

    async def execute(
        self,
        user_id: UUID,
        new_password: str,
        current_password: str | None = None,
    ) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if user.password_hash is not None:
            if current_password is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "CURRENT_PASSWORD_REQUIRED",
                        "message": "Debes proporcionar tu contraseña actual para cambiarla.",
                    },
                )
            if hash_password(current_password) != user.password_hash:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "WRONG_CURRENT_PASSWORD",
                        "message": "La contraseña actual es incorrecta.",
                    },
                )

        updated = User(
            id=user.id,
            email=user.email,
            password_hash=hash_password(new_password),
            role=user.role,
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
class LinkSocialIdentity:
    """Vincula una identidad social (Firebase) a una cuenta existente.

    Flujo:
    1. Verifica el Firebase ID Token.
    2. Si el firebase_uid ya está vinculado a ESTE usuario → idempotente, OK.
    3. Si el firebase_uid ya está vinculado a OTRO usuario → 409.
    4. Si no existe → crea el vínculo.
    """

    repo: UserRepository
    social_repo: SocialIdentityRepository
    oauth_provider: OAuthProvider

    async def execute(self, user_id: UUID, id_token: str) -> SocialIdentity:
        profile = await self.oauth_provider.exchange_token("firebase", id_token)

        existing = await self.social_repo.get_by_firebase_uid(profile["provider_user_id"])
        if existing:
            if existing.user_id == user_id:
                return existing  # ya vinculado, idempotente
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SOCIAL_ACCOUNT_ALREADY_LINKED",
                    "message": "Esta cuenta de Google ya está vinculada a otro usuario.",
                },
            )

        identity = SocialIdentity.new(
            user_id=user_id,
            provider=profile["sign_in_provider"],
            firebase_uid=profile["provider_user_id"],
        )
        await self.social_repo.add(identity)
        return identity
