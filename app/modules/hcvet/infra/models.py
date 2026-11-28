"""Tablas de la integración con HCVet (feature 0028). Migración ``f4b2c8e1a7d3``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HcvetConsentimientoModel(Base):
    """Evidencia de cada decisión del cliente. **Solo inserción**: el estado actual es la última fila de cada tipo.

    Conserva qué decidió, sobre qué versión del texto, cuándo, por qué canal y desde dónde (IP y agente de usuario).
    """

    __tablename__ = "hcvet_consentimientos"
    __table_args__ = (Index("ix_hcvet_consentimientos_user_tipo", "user_id", "tipo", "registrado_en"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    concedido: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version_texto: Mapped[str] = mapped_column(String(50), nullable=False)
    finalidad: Mapped[str] = mapped_column(String(200), nullable=False)
    canal: Mapped[str] = mapped_column(String(10), nullable=False)  # web | app
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    registrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class HcvetVinculoModel(Base):
    """Referencia del cliente en HCVet. Una fila por usuario, creada al autorizar la integración.

    ``hcvet_propietario_id`` llega en el alta y en la vinculación (HCVet D-105). ``acceso``: ``completo`` o ``basico``
    (vinculado a un propietario que ya existía: sin acceso a su información previa hasta que el dueño lo amplíe).
    """

    __tablename__ = "hcvet_vinculos"

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                                          primary_key=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    detalle: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    hcvet_propietario_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hcvet_autorizacion_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dni_vinculado: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    nuevo_en_hcvet: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    acceso: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    vinculado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class HcvetOperacionModel(Base):
    """Outbox de operaciones hacia HCVet (REQUIREMENTS §11). Se escribe en la misma transacción que el cambio en Paku.

    ``payload`` guarda solo referencias (tipo de consentimiento, campos, ids), nunca datos personales: los valores se
    leen del usuario al enviar.
    """

    __tablename__ = "hcvet_operaciones"
    __table_args__ = (
        Index("ix_hcvet_operaciones_estado_proximo", "estado", "proximo_intento_en"),
        Index("ix_hcvet_operaciones_user", "user_id", "creado_en"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=False)
    entidad: Mapped[str] = mapped_column(String(20), nullable=False, default="propietario")
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    clave_idempotencia: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    id_externo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    motivo: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    ultimo_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reintentable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    proximo_intento_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    sincronizado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
