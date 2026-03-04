from __future__ import annotations

import firebase_admin
from firebase_admin import auth as firebase_auth

from app.modules.iam.domain.oauth_provider import OAuthProfile


class FirebaseOAuthProvider:
    """Implementación del proveedor OAuth usando Firebase Admin SDK.

    Verifica el ID Token emitido por Firebase en el dispositivo móvil
    y normaliza los claims en un OAuthProfile estándar.

    El ID Token contiene el proveedor real (google.com / apple.com / facebook.com)
    en firebase.sign_in_provider — el backend no necesita que el cliente lo declare.
    """

    async def exchange_token(self, provider: str, token: str) -> OAuthProfile:
        try:
            decoded = firebase_auth.verify_id_token(token)
        except firebase_admin.exceptions.FirebaseError as exc:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Firebase token",
            ) from exc

        # Normalizar claims de Firebase → OAuthProfile
        firebase_info = decoded.get("firebase", {})
        sign_in_provider = firebase_info.get("sign_in_provider", provider)

        return OAuthProfile(
            email=decoded["email"],
            provider_user_id=decoded["uid"],
            display_name=decoded.get("name", ""),
            photo_url=decoded.get("picture"),
            sign_in_provider=sign_in_provider,
        )
