from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProviderOptionOut(BaseModel):
    value: str
    label: str


class EmailIntegrationOut(BaseModel):
    provider: str
    providers: list[ProviderOptionOut]
    enabled: bool
    configured: bool
    api_key_mask: Optional[str] = Field(None, description="Nunca la key completa, p. ej. `re_12…9aXz`.")
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    status: str = Field(..., description="not_configured | disabled | active | error (falló la última prueba)")
    last_test_at: Optional[datetime] = None
    last_test_ok: Optional[bool] = None
    last_test_error: Optional[str] = None
    encryption_ready: bool = Field(..., description="false: falta CREDENTIALS_ENCRYPTION_KEY en el servidor.")
    updated_at: Optional[datetime] = None
    updated_by: Optional[UUID] = None


class EmailIntegrationIn(BaseModel):
    provider: str = "resend"
    enabled: bool = False
    api_key: Optional[str] = Field(None, description="Vacía o ausente: se conserva la guardada.")
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None


class TestEmailIn(BaseModel):
    to: Optional[str] = Field(None, description="Sin valor: el correo del admin que prueba.")


class TestEmailOut(BaseModel):
    ok: bool
    to: str
    provider_message_id: Optional[str] = None
    error: Optional[str] = None
