"""órdenes: cobro registrado a mano por un admin (C-63)

- orders.payment_note, payment_registered_by, payment_registered_at: nota, quién y cuándo se registró un cobro hecho
  fuera de la app (efectivo, transferencia u otro). payment_method admite además "transfer" y "other" (String(10),
  sin cambio de columna).

Columnas nuevas nulas, sin backfill.

Revision ID: 2d3e4f5a6b7c
Revises: 1c2d3e4f5a6b
Create Date: 2026-11-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d3e4f5a6b7c"
down_revision: Union[str, None] = "1c2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("payment_note", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("payment_registered_by", sa.Uuid(), nullable=True))
    op.add_column("orders", sa.Column("payment_registered_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "payment_registered_at")
    op.drop_column("orders", "payment_registered_by")
    op.drop_column("orders", "payment_note")
