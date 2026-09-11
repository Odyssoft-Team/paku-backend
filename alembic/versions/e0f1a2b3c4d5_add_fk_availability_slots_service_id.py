"""add FK availability_slots.service_id -> store_products.id

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_availability_slots_service_id",
        "availability_slots",
        "store_products",
        ["service_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_availability_slots_service_id", "availability_slots", type_="foreignkey")
