"""libro de reclamaciones virtual (feature 0022)

- complaints: hojas de reclamación (datos del consumidor, del bien, el reclamo o queja, copia de los datos del
  proveedor, plazo y respuesta). Correlativo único por año.
- complaint_counters: último correlativo usado por año.

Revision ID: 9a0b1c2d3e4f
Revises: 8f9a0b1c2d3e
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a0b1c2d3e4f"
down_revision: Union[str, None] = "8f9a0b1c2d3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "complaint_counters",
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "complaints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("consumer_name", sa.String(150), nullable=False),
        sa.Column("doc_type", sa.String(20), nullable=False),
        sa.Column("doc_number", sa.String(12), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("is_minor", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("guardian_name", sa.String(150), nullable=True),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("item_description", sa.Text(), nullable=False),
        sa.Column("order_reference", sa.String(60), nullable=True),
        sa.Column("amount_claimed", sa.Numeric(12, 2), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("provider_legal_name", sa.String(200), nullable=False),
        sa.Column("provider_ruc", sa.String(11), nullable=False),
        sa.Column("provider_address", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("response_due", sa.Date(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_by", sa.Uuid(), nullable=True),
        sa.UniqueConstraint("year", "number", name="uq_complaints_year_number"),
    )
    op.create_index("ix_complaints_status_created", "complaints", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_complaints_status_created", table_name="complaints")
    op.drop_table("complaints")
    op.drop_table("complaint_counters")
