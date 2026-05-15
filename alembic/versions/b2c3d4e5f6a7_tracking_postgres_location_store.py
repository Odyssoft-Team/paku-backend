"""tracking: migrate location store from memory to PostgreSQL

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-15

Crea la tabla ally_locations para persistir la última posición conocida
del ally por orden, reemplazando el almacenamiento en memoria (LocationStore).

Diseño:
  - Una sola fila por order_id (upsert). No es historial, es snapshot.
  - El ally reporta su posición cada 10 segundos; el upsert sobreescribe.
  - Sin FK a orders para evitar acoplamiento entre módulos.
    La integridad referencial se garantiza en la capa de aplicación.
  - Compatible con múltiples instancias de Cloud Run (sin estado en memoria).

Columnas:
  - order_id:    UUID, PK (una sola fila por orden activa)
  - ally_id:     UUID del groomer asignado
  - lat:         Latitud WGS-84
  - lng:         Longitud WGS-84
  - accuracy_m:  Precisión GPS en metros (nullable, viene del SDK móvil)
  - recorded_at: Timestamp UTC del último reporte del ally
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ally_locations",
        sa.Column("order_id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("ally_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Índice en ally_id para queries del tipo "¿dónde están todos mis allies activos?"
    op.create_index("ix_ally_locations_ally_id", "ally_locations", ["ally_id"])


def downgrade() -> None:
    op.drop_index("ix_ally_locations_ally_id", table_name="ally_locations")
    op.drop_table("ally_locations")
