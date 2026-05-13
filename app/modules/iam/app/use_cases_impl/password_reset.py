"""Use cases para recuperación y restablecimiento de contraseña.

Flujo:
1. POST /auth/forgot-password  → ForgotPassword.execute(email)
   - Genera un JWT de tipo "reset" con expiración de 15 minutos.
   - En producción este token se enviaría por email; aquí se registra en logs
     como placeholder hasta integrar un proveedor de email (SES, SendGrid, etc.).
   - Siempre devuelve 200 para no revelar si el email existe.

2. POST /auth/reset-password   → ResetPassword.execute(token, new_password)
   - Valida firma y expiración del JWT.
   - Verifica que el tipo sea "reset" (evita reutilizar access/refresh tokens).
   - Hashea la nueva contraseña con bcrypt y la persiste.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import HTTPException, status

from app.core.auth import _b64url_decode, _b64url_encode, _encode, _sign, decode_token, hash_password
from app.core.settings import settings
from app.modules.iam.domain.user import UserRepository

logger = logging.getLogger(__name__)

_RESET_TOKEN_MINUTES = 15


def _create_reset_token(user_id: str, email: str) -> str:
    """Genera un JWT firmado de tipo 'reset' con expiración corta."""
    import json

    exp = datetime.now(timezone.utc) + timedelta(minutes=_RESET_TOKEN_MINUTES)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "type": "reset",
        "exp": exp.timestamp(),
    }
    return _encode(payload)


@dataclass
class ForgotPassword:
    repo: UserRepository

    async def execute(self, email: str) -> None:
        """Genera un token de reset para el email dado.

        Siempre responde con éxito para no exponer si el email existe.
        """
        user = await self.repo.get_by_email(email)
        if user is None:
            # No revelar si el email existe o no
            logger.info("forgot_password requested for unknown email (silenced)")
            return

        if not user.is_active:
            logger.info("forgot_password requested for inactive user (silenced)")
            return

        token = _create_reset_token(str(user.id), user.email)

        # TODO: Enviar token por email (integrar SES / SendGrid)
        # Por ahora se registra en logs de nivel WARNING para uso en desarrollo.
        logger.warning(
            "PASSWORD RESET TOKEN (dev only — replace with email delivery): "
            "user_id=%s email=%s token=%s",
            user.id,
            user.email,
            token,
        )


@dataclass
class ResetPassword:
    repo: UserRepository

    async def execute(self, token: str, new_password: str) -> None:
        """Valida el token de reset y actualiza la contraseña."""
        # decode_token lanza HTTPException 401 si el token es inválido o expirado
        try:
            payload = decode_token(token)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El enlace de recuperación es inválido o ha expirado",
            )

        if payload.get("type") != "reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de tipo incorrecto",
            )

        user_id: str = payload.get("sub", "")
        user = await self.repo.get_by_id(user_id)  # type: ignore[arg-type]
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario no encontrado o inactivo",
            )

        new_hash = hash_password(new_password)
        await self.repo.update_password(user.id, new_hash)

        logger.info("Password reset completed for user_id=%s", user.id)
