"""costo del groomer (feature 0012)

- groomer_cost_profiles: sueldo, cargos de la empresa (JSON), horas al mes y bolsón de manejo y reposo de
  cada groomer, vigente desde una fecha (uno por groomer y fecha).
Tabla nueva, sin backfill.

Revision ID: 1e2f3a4b5c6d
Revises: 0d1e2f3a4b5c
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1e2f3a4b5c6d"
down_revision: Union[str, None] = "0d1e2f3a4b5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groomer_cost_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("groomer_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("base_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("monthly_hours", sa.Numeric(6, 2), nullable=False),
        sa.Column("driving_rest_hours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_groomer_cost_profiles_groomer_id", "groomer_cost_profiles", ["groomer_id"])
    op.create_index(
        "ix_groomer_cost_profiles_groomer_date", "groomer_cost_profiles", ["groomer_id", "effective_from"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_groomer_cost_profiles_groomer_date", table_name="groomer_cost_profiles")
    op.drop_index("ix_groomer_cost_profiles_groomer_id", table_name="groomer_cost_profiles")
    op.drop_table("groomer_cost_profiles")
