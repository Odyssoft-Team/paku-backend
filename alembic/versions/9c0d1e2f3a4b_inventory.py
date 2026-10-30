"""inventario: insumos, movimientos y recetas (feature 0009)

- inventory_supplies: maestro de insumos (código INS-001, costo de compra, stock mínimo).
- inventory_movements: movimientos con signo; el stock es su suma. Guardan el costo por unidad del momento.
- inventory_recipes / inventory_recipe_cells / inventory_recipe_lines: una tabla por servicio o adicional
  (pelaje × tramo de peso, como los precios) con insumos y minutos de groomer por celda; versionadas (una
  fila de inventory_recipes por versión).
Tablas nuevas, sin backfill.

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c0d1e2f3a4b"
down_revision: Union[str, None] = "8b9c0d1e2f3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_supplies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sku", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("purchase_unit", sa.String(50), nullable=False),
        sa.Column("purchase_content", sa.Numeric(14, 3), nullable=False),
        sa.Column("consumption_unit", sa.String(20), nullable=False),
        sa.Column("purchase_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_stock", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("tracks_lot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tracks_expiry", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("seq", sa.Integer(), sa.Identity(), nullable=False, unique=True),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("supply_id", sa.Uuid(), sa.ForeignKey("inventory_supplies.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 6), nullable=False),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("cost_center", sa.String(30), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("recipe_id", sa.Uuid(), nullable=True),
        sa.Column("recipe_cell_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("lot", sa.String(60), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_movements_supply_id", "inventory_movements", ["supply_id"])
    op.create_index("ix_inventory_movements_order_id", "inventory_movements", ["order_id"])
    op.create_index("ix_inventory_movements_occurred_on", "inventory_movements", ["occurred_on"])
    op.create_index("ix_inventory_movements_order_type", "inventory_movements", ["order_id", "type"])

    op.create_table(
        "inventory_recipes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("target_type", sa.String(10), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_recipes_target_id", "inventory_recipes", ["target_id"])
    op.create_index("ix_inventory_recipes_target_version", "inventory_recipes", ["target_id", "version"], unique=True)

    op.create_table(
        "inventory_recipe_cells",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recipe_id", sa.Uuid(), sa.ForeignKey("inventory_recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("breed_category", sa.String(30), nullable=False),
        sa.Column("weight_min", sa.Float(), nullable=False),
        sa.Column("weight_max", sa.Float(), nullable=True),
        sa.Column("labor_minutes", sa.Numeric(8, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_inventory_recipe_cells_recipe_id", "inventory_recipe_cells", ["recipe_id"])

    op.create_table(
        "inventory_recipe_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cell_id", sa.Uuid(), sa.ForeignKey("inventory_recipe_cells.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supply_id", sa.Uuid(), sa.ForeignKey("inventory_supplies.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
    )
    op.create_index("ix_inventory_recipe_lines_cell_id", "inventory_recipe_lines", ["cell_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_recipe_lines_cell_id", table_name="inventory_recipe_lines")
    op.drop_table("inventory_recipe_lines")
    op.drop_index("ix_inventory_recipe_cells_recipe_id", table_name="inventory_recipe_cells")
    op.drop_table("inventory_recipe_cells")
    op.drop_index("ix_inventory_recipes_target_version", table_name="inventory_recipes")
    op.drop_index("ix_inventory_recipes_target_id", table_name="inventory_recipes")
    op.drop_table("inventory_recipes")
    op.drop_index("ix_inventory_movements_order_type", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_occurred_on", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_order_id", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_supply_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_supplies")
