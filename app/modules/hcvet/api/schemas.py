from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DecisionIn(BaseModel):
    tipo: str = Field(max_length=40)
    # Sin valor por defecto: cada consentimiento se decide explícitamente (REQUIREMENTS §6).
    concedido: bool
    # Versión del texto que el cliente leyó; si ya no es la vigente → 409 CONSENT_TEXT_OUTDATED.
    version_texto: str = Field(max_length=50)


class DecisionesIn(BaseModel):
    canal: Literal["web", "app"]
    decisiones: list[DecisionIn] = Field(min_length=1, max_length=5)


class DecisionOut(BaseModel):
    concedido: bool
    version_texto: str
    registrado_en: datetime


class ConsentimientoOut(BaseModel):
    tipo: str
    titulo: str
    texto: str
    version_texto: str
    decision: Optional[DecisionOut]


class IntegracionOut(BaseModel):
    # sin_autorizar | pendiente | bloqueado | sincronizando | vinculado | fallido | conflicto | revocado
    estado: str
    motivo: Optional[str]
    faltan: list[str]
    vinculado_en: Optional[datetime]
    # Solo con estado "vinculado": "completo" o "basico" (HCVet D-105).
    acceso: Optional[str] = None


class EstadoHcvetOut(BaseModel):
    integracion: IntegracionOut
    operaciones_pendientes: int
    textos_aprobados: bool
    consentimientos: list[ConsentimientoOut]


class OperacionOut(BaseModel):
    id: UUID
    user_id: UUID
    entidad: str
    tipo: str
    estado: str
    motivo: Optional[str]
    ultimo_error: Optional[str]
    intentos: int
    reintentable: bool
    id_externo: Optional[str]
    proximo_intento_en: Optional[datetime]
    creado_en: datetime
    actualizado_en: datetime
    sincronizado_en: Optional[datetime]

    model_config = {"from_attributes": True}
