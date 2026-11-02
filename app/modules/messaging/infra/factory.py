"""Factory de proveedores de correo: código del proveedor + credencial → instancia de `BaseEmailProvider`.

Agregar un proveedor = implementarlo y registrarlo aquí (y en `EMAIL_PROVIDERS` para que el admin lo vea).
"""
from __future__ import annotations

from typing import Callable

from app.modules.messaging.domain.email import BaseEmailProvider
from app.modules.messaging.infra.resend_provider import ResendEmailProvider

EMAIL_PROVIDER_REGISTRY: dict[str, Callable[[str], BaseEmailProvider]] = {
    "resend": ResendEmailProvider,
}


def build_email_provider(code: str, api_key: str) -> BaseEmailProvider:
    try:
        return EMAIL_PROVIDER_REGISTRY[code](api_key)
    except KeyError as exc:
        raise ValueError(f"Proveedor de correo desconocido: {code}") from exc
