"""proveedor de facturación electrónica (feature 0020)

- invoicing_providers: una fila por proveedor (`nubefact`): activo, ruta de la cuenta, token cifrado (Fernet) y su
  máscara, serie de boletas y última prueba de conexión. Tabla nueva, sin backfill.

Revision ID: 6d7e8f9a0b1c
Revises: 5c6d7e8f9a0b
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6d7e8f9a0b1c"
down_revision: Union[str, None] = "5c6d7e8f9a0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoicing_providers",
        sa.Column("provider", sa.String(30), primary_key=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("api_url", sa.String(300), nullable=True),
        sa.Column("token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_mask", sa.String(20), nullable=True),
        sa.Column("boleta_series", sa.String(4), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.String(500), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("invoicing_providers")
