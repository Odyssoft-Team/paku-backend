from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.modules.iam.domain.oauth_provider import OAuthProvider
from app.modules.iam.domain.social_identity import SocialIdentity, SocialIdentityRepository
from app.modules.iam.domain.user import User, UserRepository


@dataclass
class SocialLogin:
    """Autentica o registra un usuario a partir de un Firebase ID Token.

    Flujo:
    1. Verifica el token con Firebase → obtiene email, uid, nombre, foto
    2. Si el firebase_uid ya está vinculado → devuelve el usuario local
    3. Si no está vinculado pero el email existe → 409 EMAIL_ALREADY_REGISTERED
       (el usuario tiene cuenta con contraseña; debe iniciar sesión normalmente)
    4. Si es usuario completamente nuevo → crea usuario social + vincula identidad

    Devuelve (user, is_new_user).
    """

    repo: UserRepository
    social_repo: SocialIdentityRepository
    oauth_provider: OAuthProvider

    async def execute(self, id_token: str) -> tuple[User, bool]:
        profile = await self.oauth_provider.exchange_token("firebase", id_token)

        # 1. Buscar por firebase_uid — identidad fuerte, sin ambigüedad
        existing_identity = await self.social_repo.get_by_firebase_uid(profile["provider_user_id"])
        if existing_identity:
            user = await self.repo.get_by_id(existing_identity.user_id)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is inactive",
                )
            return user, False

        # 2. El firebase_uid no existe. Verificar si el email ya tiene cuenta local.
        #    No se hace auto-link — el usuario debe confirmar explícitamente.
        existing_user = await self.repo.get_by_email(profile["email"])
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "EMAIL_ALREADY_REGISTERED",
                    "message": "Este correo ya tiene una cuenta. Inicia sesión con tu contraseña.",
                },
            )

        # 3. Usuario nuevo — crear con perfil incompleto
        display_name = profile.get("display_name") or ""
        parts = display_name.split(" ", 1)
        first_name = parts[0] if parts[0] else "Usuario"
        last_name = parts[1] if len(parts) > 1 else ""

        user = User.new_social(
            email=profile["email"],
            first_name=first_name,
            last_name=last_name,
            profile_photo_url=profile.get("photo_url"),
        )
        await self.repo.add(user)

        identity = SocialIdentity.new(
            user_id=user.id,
            provider=profile["sign_in_provider"],
            firebase_uid=profile["provider_user_id"],
        )
        await self.social_repo.add(identity)

        return user, True
