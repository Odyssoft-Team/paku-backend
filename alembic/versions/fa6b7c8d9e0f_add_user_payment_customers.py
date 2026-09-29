"""wallet: map users to external payment customers

Revision ID: fa6b7c8d9e0f
Revises: e0f1a2b3c4d5
Create Date: 2026-09-28

Creates a unique provider/customer mapping with a durable provisioning state.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fa6b7c8d9e0f"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_payment_customers",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="provisioning"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_user_payment_customers_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "(status = 'provisioning' AND customer_id IS NULL) "
            "OR (status = 'ready' AND customer_id IS NOT NULL)",
            name="ck_user_payment_customers_status_customer_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "provider", name="uq_user_payment_customers_user_provider"
        ),
    )


def downgrade() -> None:
    op.drop_table("user_payment_customers")