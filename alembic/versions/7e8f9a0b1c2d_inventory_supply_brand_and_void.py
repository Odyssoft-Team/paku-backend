"""insumos: marca, descripción y proveedores; precio en la compra; anulación de movimientos (feature 0021)

- inventory_supplies: `brand` y `description` opcionales; `suppliers` (JSON, lista de proveedores del insumo,
  por defecto `[]`).
- inventory_movements: `purchase_quantity` y `purchase_price` (entrada con precio, S/ por unidad de compra);
  `voided_at`, `voided_by`, `void_reason`. Null = vigente; los anulados no cuentan en el stock.
- Sin backfill: los insumos existentes quedan sin marca, sin descripción y sin proveedores.

Revision ID: 7e8f9a0b1c2d
Revises: 6d7e8f9a0b1c
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e8f9a0b1c2d"
down_revision: Union[str, None] = "6d7e8f9a0b1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inventory_supplies", sa.Column("brand", sa.String(100), nullable=True))
    op.add_column("inventory_supplies", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "inventory_supplies",
        sa.Column("suppliers", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("inventory_movements", sa.Column("purchase_quantity", sa.Numeric(14, 3), nullable=True))
    op.add_column("inventory_movements", sa.Column("purchase_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("inventory_movements", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("inventory_movements", sa.Column("voided_by", sa.Uuid(), nullable=True))
    op.add_column("inventory_movements", sa.Column("void_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_movements", "void_reason")
    op.drop_column("inventory_movements", "voided_by")
    op.drop_column("inventory_movements", "voided_at")
    op.drop_column("inventory_movements", "purchase_price")
    op.drop_column("inventory_movements", "purchase_quantity")
    op.drop_column("inventory_supplies", "suppliers")
    op.drop_column("inventory_supplies", "description")
    op.drop_column("inventory_supplies", "brand")
