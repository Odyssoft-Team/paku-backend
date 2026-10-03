"""orders: proceso del servicio (pasos, addons realizados) y fotos de la orden

Pedidos 3 y 6 de la app Groomer (docs/pedidos-al-backend.md):
  - orders.service_step      VARCHAR(20) NULL  — paso actual (reception, bath, drying, finishing, return)
  - orders.service_steps_log JSON NULL         — [{step, started_at}]
  - orders.addons_done       JSON NULL         — [{addon_id, done_at}]
  - order_photos                               — fotos initial / final / incident subidas por el groomer

Escrita sin conexión a la BD (no ejecutada aún).

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-10-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b3c4d5e6f7a"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("service_step", sa.String(20), nullable=True))
    op.add_column("orders", sa.Column("service_steps_log", sa.JSON(), nullable=True))
    op.add_column("orders", sa.Column("addons_done", sa.JSON(), nullable=True))

    op.create_table(
        "order_photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("object_name", sa.String(300), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_order_photos_order_id", "order_photos", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_photos_order_id", table_name="order_photos")
    op.drop_table("order_photos")
    op.drop_column("orders", "addons_done")
    op.drop_column("orders", "service_steps_log")
    op.drop_column("orders", "service_step")
