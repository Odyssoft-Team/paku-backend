"""orders: peso medido, monto extra y orden de ajuste (feature 0003-saldo-por-peso)

- measured_weight_kg / measured_weight_at: peso que registró el groomer (o un admin) en el servicio.
- extra_charge: diferencia a cobrar si ese peso da un precio mayor; null si no hay.
- adjustment_order_id: orden de ajuste generada por el admin (evita un segundo cobro).

Sin backfill: las órdenes existentes quedan en null.

Escrita sin conexión a la BD (no ejecutada aún).

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5e6f7a8b9c0d"
down_revision: Union[str, None] = "4d5e6f7a8b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("measured_weight_kg", sa.Numeric(6, 2), nullable=True))
    op.add_column("orders", sa.Column("measured_weight_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("extra_charge", sa.Numeric(12, 2), nullable=True))
    op.add_column("orders", sa.Column("adjustment_order_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "adjustment_order_id")
    op.drop_column("orders", "extra_charge")
    op.drop_column("orders", "measured_weight_at")
    op.drop_column("orders", "measured_weight_kg")
