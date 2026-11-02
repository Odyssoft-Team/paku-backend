"""capturas del inventario (feature 0015)

- inventory_snapshots: foto del inventario en una fecha de corte (automática según Parámetros generales o
  manual). `schedule_key` único = una sola automática por corte.
- inventory_snapshot_lines: stock, mínimo, costo, valor y estado de cada insumo al corte, con copia de sus datos.
Tablas nuevas, sin backfill.

Revision ID: 3a4b5c6d7e8f
Revises: 2f3a4b5c6d7e
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3a4b5c6d7e8f"
down_revision: Union[str, None] = "2f3a4b5c6d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cut_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=True),
        sa.Column("schedule_key", sa.String(20), nullable=True, unique=True),
        sa.Column("supplies_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("low_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("out_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_snapshots_cut_date", "inventory_snapshots", ["cut_date"])
    op.create_table(
        "inventory_snapshot_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("inventory_snapshots.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("supply_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("consumption_unit", sa.String(20), nullable=False),
        sa.Column("purchase_unit", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("stock", sa.Numeric(14, 3), nullable=False),
        sa.Column("min_stock", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 6), nullable=False),
        sa.Column("value", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
    )
    op.create_index("ix_inventory_snapshot_lines_snapshot_id", "inventory_snapshot_lines", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_snapshot_lines_snapshot_id", table_name="inventory_snapshot_lines")
    op.drop_table("inventory_snapshot_lines")
    op.drop_index("ix_inventory_snapshots_cut_date", table_name="inventory_snapshots")
    op.drop_table("inventory_snapshots")
