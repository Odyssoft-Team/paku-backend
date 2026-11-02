"""Cifrado de credenciales de integraciones (feature 0018) con Fernet (AES-128-CBC + HMAC-SHA256).

La llave sale de `CREDENTIALS_ENCRYPTION_KEY`. Admite varias separadas por coma para rotarlas: la primera cifra y
todas descifran. Sin llave el backend arranca igual, pero no se pueden guardar ni leer credenciales.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CryptoUnavailable(Exception):
    """Falta la llave o no es válida, o el dato cifrado no se puede leer con ella."""


def _fernet(raw: str | None = None) -> MultiFernet:
    if raw is None:
        from app.core.settings import settings

        raw = settings.CREDENTIALS_ENCRYPTION_KEY
    keys = [k.strip() for k in (raw or "").split(",") if k.strip()]
    if not keys:
        raise CryptoUnavailable("Falta CREDENTIALS_ENCRYPTION_KEY en el servidor.")
    try:
        return MultiFernet([Fernet(k) for k in keys])
    except (ValueError, TypeError) as exc:
        raise CryptoUnavailable("CREDENTIALS_ENCRYPTION_KEY no es una llave Fernet válida.") from exc


def encryption_ready() -> bool:
    try:
        _fernet()
        return True
    except CryptoUnavailable:
        return False


def encrypt_secret(plain: str, *, key: str | None = None) -> str:
    return _fernet(key).encrypt(plain.encode()).decode()


def decrypt_secret(token: str, *, key: str | None = None) -> str:
    try:
        return _fernet(key).decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise CryptoUnavailable("La credencial guardada no se puede descifrar con la llave actual.") from exc
