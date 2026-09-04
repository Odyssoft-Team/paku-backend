"""replace pets.breed (free text) with breed_id (FK to breeds) + breed_name

Revision ID: a6b7c8d9e0f1
Revises: d4e5f6a7b8c9
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pets", sa.Column("breed_id", sa.String(100), nullable=True))
    op.add_column("pets", sa.Column("breed_name", sa.String(200), nullable=True))
    op.create_foreign_key(
        "fk_pets_breed_id_breeds",
        "pets",
        "breeds",
        ["breed_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_pets_breed_id", "pets", ["breed_id"])
    op.drop_column("pets", "breed")


def downgrade() -> None:
    op.add_column("pets", sa.Column("breed", sa.String(100), nullable=True))
    op.drop_index("ix_pets_breed_id", table_name="pets")
    op.drop_constraint("fk_pets_breed_id_breeds", "pets", type_="foreignkey")
    op.drop_column("pets", "breed_name")
    op.drop_column("pets", "breed_id")
