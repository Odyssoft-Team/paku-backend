"""Correo saliente (feature 0018): mensaje, resultado, interfaz del proveedor y reglas de la configuración.

El resto del backend no sabe qué proveedor hay detrás: arma un `EmailMessage` y lo entrega a un
`BaseEmailProvider` obtenido de la factory (`infra/factory.py`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from email_validator import EmailNotValidError, validate_email

EMAIL_CHANNEL = "email"

# Proveedores que el admin puede elegir: código → nombre visible.
EMAIL_PROVIDERS: dict[str, str] = {"resend": "Resend"}

# Prefijo de las API keys de cada proveedor, para avisar si se pegó otra cosa.
API_KEY_PREFIX: dict[str, str] = {"resend": "re_"}

FROM_NAME_MAX = 100


@dataclass(frozen=True)
class EmailMessage:
    to: list[str]
    subject: str
    html: Optional[str] = None
    text: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Sender:
    from_email: str
    from_name: Optional[str] = None
    reply_to: Optional[str] = None

    @property
    def formatted(self) -> str:
        return f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email


@dataclass(frozen=True)
class SendResult:
    provider_message_id: Optional[str]


class EmailProviderError(Exception):
    """El proveedor rechazó el envío. `retryable`: falla temporal (límite de envíos, caída) que vale reintentar."""

    def __init__(self, message: str, *, retryable: bool = False, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class BaseEmailProvider(ABC):
    code: str

    @abstractmethod
    async def send(self, message: EmailMessage, *, sender: Sender,
                   idempotency_key: Optional[str] = None) -> SendResult:
        """Envía el mensaje. Lanza `EmailProviderError` si el proveedor lo rechaza."""


class EmailConfigInvalid(Exception):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def normalize_email(value: str, *, field: str) -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise EmailConfigInvalid(field, f"«{value}» no es un correo válido.") from exc


def check_api_key(provider: str, api_key: str) -> str:
    key = api_key.strip()
    prefix = API_KEY_PREFIX.get(provider)
    if not key or any(c.isspace() for c in key):
        raise EmailConfigInvalid("api_key", "La API key no puede estar vacía ni tener espacios.")
    if prefix and not key.startswith(prefix):
        raise EmailConfigInvalid("api_key", f"Las API keys de {EMAIL_PROVIDERS[provider]} empiezan con «{prefix}».")
    return key


def mask_secret(secret: str) -> str:
    """`re_12…9aXz`: primeros 5 y últimos 4. Si es corto, solo los últimos 2."""
    if len(secret) <= 12:
        return "…" + secret[-2:]
    return f"{secret[:5]}…{secret[-4:]}"
