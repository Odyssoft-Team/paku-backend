"""parámetros generales de la empresa (feature 0010)

- general_settings: clave → valor JSON. Solo se guardan los parámetros que el admin cambió; el resto usa
  su valor por defecto (definido en el código).
Tabla nueva, sin backfill.

Revision ID: 0d1e2f3a4b5c
Revises: 9c0d1e2f3a4b
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0d1e2f3a4b5c"
down_revision: Union[str, None] = "9c0d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "general_settings",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("general_settings")
