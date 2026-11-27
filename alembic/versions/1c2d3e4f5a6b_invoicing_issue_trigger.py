"""facturación: momento en que una orden queda lista para emitir (feature 0023)

- invoicing_providers.issue_trigger: `service` (al realizarse el servicio) o `payment` (al confirmarse el pago).
  La emisión automática (`auto_issue`) emite en ese momento; la manual lista las órdenes listas según él.

Columna nueva con valor por defecto `service`, sin backfill.

Revision ID: 1c2d3e4f5a6b
Revises: 0b1c2d3e4f5a
Create Date: 2026-11-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1c2d3e4f5a6b"
down_revision: Union[str, None] = "0b1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoicing_providers",
                  sa.Column("issue_trigger", sa.String(10), nullable=False, server_default="service"))


def downgrade() -> None:
    op.drop_column("invoicing_providers", "issue_trigger")
