"""users: nombres legales del DNI separados del nombre visible (feature 0027, PAKU-USERS-007)

Columnas opcionales: los nombres oficiales los llena el servidor con una consulta a Datos Perú. No son verificación
de titularidad. No toca datos existentes.

Revision ID: d2e7f1a9c4b8
Revises: 3e4f5a6b7c8d
Create Date: 2026-11-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e7f1a9c4b8"
down_revision: Union[str, None] = "3e4f5a6b7c8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("legal_first_name", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("legal_last_name", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("legal_data_source", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("legal_data_checked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "legal_data_checked_at")
    op.drop_column("users", "legal_data_source")
    op.drop_column("users", "legal_last_name")
    op.drop_column("users", "legal_first_name")
