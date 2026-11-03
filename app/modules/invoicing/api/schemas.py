from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ReadinessOut(BaseModel):
    company_ruc: Optional[str] = Field(None, description="De Parámetros generales; sin RUC no se puede emitir.")
    company_name: Optional[str] = None
    igv_percent: float
    customers: int = Field(..., description="Clientes activos.")
    customers_with_dni: int = Field(..., description="De ellos, con DNI registrado.")


class NubefactIntegrationOut(BaseModel):
    enabled: bool
    configured: bool
    api_url: Optional[str] = None
    token_mask: Optional[str] = Field(None, description="Nunca el token completo.")
    boleta_series: str
    status: str = Field(..., description="not_configured | disabled | active | error (falló la última prueba)")
    last_test_at: Optional[datetime] = None
    last_test_ok: Optional[bool] = None
    last_test_error: Optional[str] = None
    encryption_ready: bool
    updated_at: Optional[datetime] = None
    updated_by: Optional[UUID] = None
    readiness: ReadinessOut


class NubefactIntegrationIn(BaseModel):
    enabled: bool = False
    api_url: Optional[str] = Field(None, description="RUTA de la cuenta, p. ej. https://api.nubefact.com/api/v1/…")
    token: Optional[str] = Field(None, description="Vacío o ausente: se conserva el guardado.")
    boleta_series: Optional[str] = Field(None, description="4 caracteres que empiezan con B. Por defecto B001.")


class ConnectionTestOut(BaseModel):
    ok: bool
    message: str
