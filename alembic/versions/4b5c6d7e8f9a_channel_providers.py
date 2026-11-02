"""proveedores de envío por canal (feature 0018)

- channel_providers: una fila por canal (`email`): proveedor, activo, credencial cifrada (Fernet) y su máscara,
  remitente y última prueba. Tabla nueva, sin backfill.

Revision ID: 4b5c6d7e8f9a
Revises: 3a4b5c6d7e8f
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b5c6d7e8f9a"
down_revision: Union[str, None] = "3a4b5c6d7e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_providers",
        sa.Column("channel", sa.String(20), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("secret_encrypted", sa.Text(), nullable=True),
        sa.Column("secret_mask", sa.String(20), nullable=True),
        sa.Column("from_email", sa.String(254), nullable=True),
        sa.Column("from_name", sa.String(100), nullable=True),
        sa.Column("reply_to", sa.String(254), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.String(500), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("channel_providers")
