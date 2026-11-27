"""gastos operativos y vehículos (feature 0026)

- vehicles: vehículos de la empresa (nombre, placa única, marca, modelo, año, activo).
- expenses: gastos únicos, mensuales o anuales, con lo pagado, si incluye IGV, el monto sin IGV, vehículo opcional,
  proveedor, comprobante y anulación (no se borran).

Tablas nuevas, sin backfill.

Revision ID: 3e4f5a6b7c8d
Revises: 2d3e4f5a6b7c
Create Date: 2026-11-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3e4f5a6b7c8d"
down_revision: Union[str, None] = "2d3e4f5a6b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("plate", sa.String(20), nullable=True, unique=True),
        sa.Column("brand", sa.String(60), nullable=True),
        sa.Column("model", sa.String(60), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("total_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("igv_included", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("supplier", sa.String(200), nullable=True),
        sa.Column("document", sa.String(60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.Uuid(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_expenses_start_date", "expenses", ["start_date"])
    op.create_index("ix_expenses_vehicle_id", "expenses", ["vehicle_id"])


def downgrade() -> None:
    op.drop_index("ix_expenses_vehicle_id", table_name="expenses")
    op.drop_index("ix_expenses_start_date", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("vehicles")
