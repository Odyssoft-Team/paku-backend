"""iam: make users fields nullable + add profile_completed

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-03-04

Hace nullable password_hash, phone, sex y birth_date en la tabla users
para soportar usuarios registrados vía social login (Google/Apple/Facebook).
Agrega la columna profile_completed con DEFAULT TRUE para no afectar usuarios existentes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    op.alter_column("users", "phone", existing_type=sa.String(50), nullable=True)
    op.alter_column("users", "sex", existing_type=sa.String(10), nullable=True)
    op.alter_column("users", "birth_date", existing_type=sa.Date(), nullable=True)
    op.add_column(
        "users",
        sa.Column(
            "profile_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),  # TRUE para usuarios existentes (ya tienen perfil completo)
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "profile_completed")
    op.alter_column("users", "birth_date", existing_type=sa.Date(), nullable=False)
    op.alter_column("users", "sex", existing_type=sa.String(10), nullable=False)
    op.alter_column("users", "phone", existing_type=sa.String(50), nullable=False)
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
