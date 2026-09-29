"""wallet: prevent duplicate local Culqi card IDs

Revision ID: fb7c8d9e0f1a
Revises: fa6b7c8d9e0f
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fb7c8d9e0f1a"
down_revision: Union[str, None] = "fa6b7c8d9e0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_wallet_cards_provider_culqi_card_id",
        "wallet_cards",
        ["provider", "culqi_card_id"],
        unique=True,
        postgresql_where=sa.text("culqi_card_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_wallet_cards_provider_culqi_card_id", table_name="wallet_cards")