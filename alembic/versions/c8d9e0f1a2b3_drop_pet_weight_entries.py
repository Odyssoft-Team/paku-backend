"""drop pet_weight_entries — centralizado en pet_records (type=weight_record)

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-09-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_pet_weight_entries_pet_id", table_name="pet_weight_entries")
    op.drop_table("pet_weight_entries")


def downgrade() -> None:
    op.create_table(
        "pet_weight_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["pet_id"], ["pets.id"],
            name="fk_pet_weight_entries_pet_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pet_weight_entries_pet_id", "pet_weight_entries", ["pet_id"])
