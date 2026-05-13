"""wallet: create wallet_cards table

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-05-13

Crea la tabla wallet_cards para persistir las tarjetas guardadas de los usuarios.
Reemplaza el almacenamiento en memoria (InMemoryCardRepository).

Columnas nuevas respecto al modelo anterior:
  - culqi_customer_id: ID del cliente en Culqi (cus_...) para cargos One-click
  - culqi_card_id: ID de la tarjeta en Culqi (crd_...) para cargos One-click
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_cards",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("payment_method_id", sa.String(100), nullable=False),
        sa.Column("brand", sa.String(30), nullable=False),
        sa.Column("last4", sa.String(4), nullable=False),
        sa.Column("exp_month", sa.Integer(), nullable=False),
        sa.Column("exp_year", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("culqi_customer_id", sa.String(60), nullable=True),
        sa.Column("culqi_card_id", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wallet_cards_user_id", "wallet_cards", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_wallet_cards_user_id", table_name="wallet_cards")
    op.drop_table("wallet_cards")
