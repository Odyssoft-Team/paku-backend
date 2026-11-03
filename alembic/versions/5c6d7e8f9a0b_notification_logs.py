"""registro de envíos (feature 0018 fase 2)

- notification_logs: un envío por canal con `idempotency_key` única, estado PENDING/SENT/FAILED, intentos y próximo
  reintento, mensaje armado (`payload`) y referencias opcionales a usuario, orden y campaña. Tabla nueva, sin backfill.

Revision ID: 5c6d7e8f9a0b
Revises: 4b5c6d7e8f9a
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5c6d7e8f9a0b"
down_revision: Union[str, None] = "4b5c6d7e8f9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(30), nullable=True),
        sa.Column("idempotency_key", sa.String(256), nullable=False, unique=True),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("template", sa.String(50), nullable=True),
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("provider_message_id", sa.String(100), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notification_logs_created_at", "notification_logs", ["created_at"])
    op.create_index("ix_notification_logs_status_next", "notification_logs", ["status", "next_attempt_at"])
    op.create_index("ix_notification_logs_user_id", "notification_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_logs_user_id", table_name="notification_logs")
    op.drop_index("ix_notification_logs_status_next", table_name="notification_logs")
    op.drop_index("ix_notification_logs_created_at", table_name="notification_logs")
    op.drop_table("notification_logs")
