"""add pet_records table

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pet_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_by_role", sa.String(length=20), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("attachment_ids", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["pet_id"],
            ["pets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Índices individuales
    op.create_index(
        op.f("ix_pet_records_pet_id"),
        "pet_records",
        ["pet_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pet_records_type"),
        "pet_records",
        ["type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pet_records_occurred_at"),
        "pet_records",
        ["occurred_at"],
        unique=False,
    )

    # Índices compuestos
    op.create_index(
        "ix_pet_records_pet_id_type",
        "pet_records",
        ["pet_id", "type"],
        unique=False,
    )
    op.create_index(
        "ix_pet_records_pet_id_occurred_at",
        "pet_records",
        ["pet_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pet_records_pet_id_occurred_at", table_name="pet_records")
    op.drop_index("ix_pet_records_pet_id_type", table_name="pet_records")
    op.drop_index(op.f("ix_pet_records_occurred_at"), table_name="pet_records")
    op.drop_index(op.f("ix_pet_records_type"), table_name="pet_records")
    op.drop_index(op.f("ix_pet_records_pet_id"), table_name="pet_records")
    op.drop_table("pet_records")
