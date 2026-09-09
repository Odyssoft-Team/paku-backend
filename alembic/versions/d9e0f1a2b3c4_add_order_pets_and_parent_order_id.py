"""add order_pets bridge table + orders.parent_order_id (recálculo de precio por peso)

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-09-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("parent_order_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_orders_parent_order_id",
        "orders",
        "orders",
        ["parent_order_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "order_pets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_order_pets_order_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_pets_order_id", "order_pets", ["order_id"])
    op.create_index("ix_order_pets_pet_id", "order_pets", ["pet_id"])


def downgrade() -> None:
    op.drop_index("ix_order_pets_pet_id", table_name="order_pets")
    op.drop_index("ix_order_pets_order_id", table_name="order_pets")
    op.drop_table("order_pets")

    op.drop_constraint("fk_orders_parent_order_id", "orders", type_="foreignkey")
    op.drop_column("orders", "parent_order_id")
