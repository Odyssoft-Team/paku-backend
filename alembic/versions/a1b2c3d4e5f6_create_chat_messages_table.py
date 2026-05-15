"""chat: create chat_messages table

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-05-15

Crea la tabla chat_messages para el módulo de chat entre usuario y ally
durante una orden activa.

Columnas:
  - id:          UUID, PK
  - order_id:    UUID, FK lógica a orders (sin FK DB para evitar acoplamiento)
  - sender_id:   UUID del remitente (user o ally)
  - sender_role: "user" | "ally" | "admin"
  - body:        Texto del mensaje (max 2000 chars en app layer)
  - is_read:     Booleano; True cuando el destinatario leyó el mensaje
  - created_at:  Timestamp UTC con zona horaria

Índices:
  - ix_chat_messages_order_created  → query principal de polling
  - ix_chat_messages_order_unread   → conteo de no leídos
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("order_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sender_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sender_role", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_chat_messages_order_id", "chat_messages", ["order_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    op.create_index(
        "ix_chat_messages_order_created",
        "chat_messages",
        ["order_id", "created_at"],
    )
    op.create_index(
        "ix_chat_messages_order_unread",
        "chat_messages",
        ["order_id", "is_read"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_order_unread", table_name="chat_messages")
    op.drop_index("ix_chat_messages_order_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_order_id", table_name="chat_messages")
    op.drop_table("chat_messages")
