"""campañas y promociones (feature 0013)

- campaigns: descuento por público (segmento de Clientes, todos, primera compra o cumpleaños), por % o monto
  fijo o un adicional gratis; automática o con cupón; límites de uso por cliente y totales.
- campaign_redemptions: uso de una campaña en una orden (una por orden); se libera al cancelar la orden.
- orders.discount_amount / orders.campaign_id: descuento aplicado; total_snapshot pasa a ser el neto.
Sin backfill: las órdenes anteriores quedan sin descuento.

Revision ID: 2f3a4b5c6d7e
Revises: 1e2f3a4b5c6d
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2f3a4b5c6d7e"
down_revision: Union[str, None] = "1e2f3a4b5c6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("audience", sa.String(30), nullable=False),
        sa.Column("benefit_type", sa.String(20), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("addon_code", sa.String(50), nullable=True),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("automatic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_uses_per_customer", sa.Integer(), nullable=True),
        sa.Column("max_total_uses", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "campaign_redemptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_campaign_redemptions_campaign_id", "campaign_redemptions", ["campaign_id"])
    op.create_index("ix_campaign_redemptions_user_id", "campaign_redemptions", ["user_id"])
    op.add_column("orders", sa.Column("discount_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("orders", sa.Column("campaign_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "campaign_id")
    op.drop_column("orders", "discount_amount")
    op.drop_index("ix_campaign_redemptions_user_id", table_name="campaign_redemptions")
    op.drop_index("ix_campaign_redemptions_campaign_id", table_name="campaign_redemptions")
    op.drop_table("campaign_redemptions")
    op.drop_table("campaigns")
