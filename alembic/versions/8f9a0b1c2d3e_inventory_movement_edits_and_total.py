"""movimientos: total pagado en la entrada y edición con historial (feature 0021)

- inventory_movements: `purchase_total` (S/ pagado por la entrada) reemplaza a `purchase_quantity` y
  `purchase_price`. Backfill: en las entradas que tenían precio, total = cantidad × costo por unidad (el costo por
  unidad ya era precio ÷ contenido). Se agregan `edited_at` y `edited_by` (última edición).
- inventory_movement_edits: historial de ediciones (quién, cuándo, motivo y valores antes y después).

Revision ID: 8f9a0b1c2d3e
Revises: 7e8f9a0b1c2d
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f9a0b1c2d3e"
down_revision: Union[str, None] = "7e8f9a0b1c2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inventory_movements", sa.Column("purchase_total", sa.Numeric(12, 2), nullable=True))
    op.execute(
        "UPDATE inventory_movements SET purchase_total = ROUND(ABS(quantity) * unit_cost, 2) "
        "WHERE purchase_price IS NOT NULL"
    )
    op.drop_column("inventory_movements", "purchase_price")
    op.drop_column("inventory_movements", "purchase_quantity")
    op.add_column("inventory_movements", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("inventory_movements", sa.Column("edited_by", sa.Uuid(), nullable=True))
    op.create_table(
        "inventory_movement_edits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("movement_id", sa.Uuid(), sa.ForeignKey("inventory_movements.id"), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_by", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
    )
    op.create_index("ix_inventory_movement_edits_movement_id", "inventory_movement_edits", ["movement_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_movement_edits_movement_id", table_name="inventory_movement_edits")
    op.drop_table("inventory_movement_edits")
    op.drop_column("inventory_movements", "edited_by")
    op.drop_column("inventory_movements", "edited_at")
    # El precio por unidad de compra no se puede reconstruir sin el contenido del insumo: queda vacío
    op.add_column("inventory_movements", sa.Column("purchase_quantity", sa.Numeric(14, 3), nullable=True))
    op.add_column("inventory_movements", sa.Column("purchase_price", sa.Numeric(12, 2), nullable=True))
    op.drop_column("inventory_movements", "purchase_total")
