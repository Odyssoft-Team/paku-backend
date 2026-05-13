"""orders: add payment_status and culqi_charge_id

Revision ID: e3f4a5b6c7d8
Revises: 0000000000000
Create Date: 2026-06-01

Agrega dos columnas a la tabla orders para soportar el flujo de pago con Culqi:
  - payment_status: estado del pago (pending | paid | failed), NOT NULL DEFAULT 'pending'
  - culqi_charge_id: ID del cargo creado en Culqi (chr_...), nullable
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "0000000000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "payment_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "culqi_charge_id",
            sa.String(length=60),
            nullable=True,
        ),
    )
    # Índice parcial para consultar rápidamente órdenes con pago confirmado
    op.create_index(
        "ix_orders_culqi_charge_id",
        "orders",
        ["culqi_charge_id"],
        unique=True,
        postgresql_where=sa.text("culqi_charge_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_orders_culqi_charge_id", table_name="orders")
    op.drop_column("orders", "culqi_charge_id")
    op.drop_column("orders", "payment_status")
