"""hcvet: consentimientos, vínculo y cola de operaciones (feature 0028, bloque C)

Solo crea tablas nuevas; no toca ``users`` ni datos existentes.

- ``hcvet_consentimientos``: evidencia de cada decisión del cliente (solo inserción).
- ``hcvet_vinculos``: referencia del cliente en HCVet (id del propietario y de la autorización) y estado.
- ``hcvet_operaciones``: outbox de operaciones hacia HCVet con estado, intentos, clave de idempotencia y error.

Revision ID: f4b2c8e1a7d3
Revises: e8f3a1c7d5b2
Create Date: 2026-11-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4b2c8e1a7d3"
down_revision: Union[str, None] = "e8f3a1c7d5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hcvet_consentimientos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("concedido", sa.Boolean(), nullable=False),
        sa.Column("version_texto", sa.String(50), nullable=False),
        sa.Column("finalidad", sa.String(200), nullable=False),
        sa.Column("canal", sa.String(10), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('integracion_hcvet','indexacion_veterinaria','historial_compartido','registro_eventos',"
            "'uso_comercial')",
            name="ck_hcvet_consentimientos_tipo",
        ),
        sa.CheckConstraint("canal IN ('web','app')", name="ck_hcvet_consentimientos_canal"),
    )
    op.create_index(
        "ix_hcvet_consentimientos_user_tipo", "hcvet_consentimientos", ["user_id", "tipo", "registrado_en"]
    )

    op.create_table(
        "hcvet_vinculos",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("motivo", sa.String(40), nullable=True),
        sa.Column("detalle", sa.String(300), nullable=True),
        sa.Column("hcvet_propietario_id", sa.Integer(), nullable=True),
        sa.Column("hcvet_autorizacion_id", sa.Integer(), nullable=True),
        sa.Column("dni_vinculado", sa.String(8), nullable=True),
        sa.Column("nuevo_en_hcvet", sa.Boolean(), nullable=True),
        # completo | basico (HCVet D-105); nulo hasta vincularse.
        sa.Column("acceso", sa.String(10), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vinculado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('pendiente','bloqueado','sincronizando','vinculado','fallido','conflicto','revocado')",
            name="ck_hcvet_vinculos_estado",
        ),
        sa.CheckConstraint("acceso IS NULL OR acceso IN ('completo','basico')", name="ck_hcvet_vinculos_acceso"),
    )
    # Un propietario de HCVet no queda vinculado a dos cuentas de Paku.
    op.create_index(
        "uq_hcvet_vinculos_propietario", "hcvet_vinculos", ["hcvet_propietario_id"], unique=True,
        postgresql_where=sa.text("hcvet_propietario_id IS NOT NULL"),
    )

    op.create_table(
        "hcvet_operaciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entidad", sa.String(20), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("clave_idempotencia", sa.String(255), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id_externo", sa.String(50), nullable=True),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("motivo", sa.String(40), nullable=True),
        sa.Column("ultimo_error", sa.Text(), nullable=True),
        sa.Column("reintentable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("proximo_intento_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sincronizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('pendiente','bloqueado','sincronizando','sincronizado','fallido','conflicto','cancelado')",
            name="ck_hcvet_operaciones_estado",
        ),
    )
    op.create_index("ix_hcvet_operaciones_estado_proximo", "hcvet_operaciones", ["estado", "proximo_intento_en"])
    op.create_index("ix_hcvet_operaciones_user", "hcvet_operaciones", ["user_id", "creado_en"])
    # Una sola alta abierta por cliente, aunque lleguen dos decisiones a la vez.
    op.create_index(
        "uq_hcvet_operaciones_alta_abierta", "hcvet_operaciones", ["user_id"], unique=True,
        postgresql_where=sa.text(
            "tipo = 'alta_propietario' AND estado IN ('pendiente','bloqueado','sincronizando','fallido')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_hcvet_operaciones_alta_abierta", table_name="hcvet_operaciones")
    op.drop_index("ix_hcvet_operaciones_user", table_name="hcvet_operaciones")
    op.drop_index("ix_hcvet_operaciones_estado_proximo", table_name="hcvet_operaciones")
    op.drop_table("hcvet_operaciones")
    op.drop_index("uq_hcvet_vinculos_propietario", table_name="hcvet_vinculos")
    op.drop_table("hcvet_vinculos")
    op.drop_index("ix_hcvet_consentimientos_user_tipo", table_name="hcvet_consentimientos")
    op.drop_table("hcvet_consentimientos")
