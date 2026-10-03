"""orders: parada saltada (skipped) y avisos de demora

Pedidos 4 y 5 de la app Groomer (docs/pedidos-al-backend.md):
  - orders.skip_reason VARCHAR(30) NULL  — pet_not_present | tutor_not_present | other
  - orders.skip_note   TEXT NULL
  - orders.skipped_at  TIMESTAMPTZ NULL
  - order_delay_reports                  — avisos de demora (tráfico) del groomer
El nuevo estado "skipped" no requiere DDL: orders.status es VARCHAR.

Escrita sin conexión a la BD (no ejecutada aún).

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-10-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c4d5e6f7a8b"
down_revision: Union[str, None] = "2b3c4d5e6f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("skip_reason", sa.String(30), nullable=True))
    op.add_column("orders", sa.Column("skip_note", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "order_delay_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("groomer_id", sa.Uuid(), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_order_delay_reports_order_id", "order_delay_reports", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_delay_reports_order_id", table_name="order_delay_reports")
    op.drop_table("order_delay_reports")
    op.drop_column("orders", "skipped_at")
    op.drop_column("orders", "skip_note")
    op.drop_column("orders", "skip_reason")
