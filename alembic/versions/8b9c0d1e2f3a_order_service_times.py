"""orders: tiempos de atención del groomer (C-32)

- departed_at: cuándo salió hacia el domicilio (status on_the_way).
- completed_at: cuándo terminó el servicio (status done).
Con service_steps_log (inicio de cada paso) se calcula traslado, duración por paso y total.
Sin backfill: las órdenes anteriores quedan en null.

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b9c0d1e2f3a"
down_revision: Union[str, None] = "7a8b9c0d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "completed_at")
    op.drop_column("orders", "departed_at")
