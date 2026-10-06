"""orders.reserved_date: día de la reserva de cupo vigente (C-21)

Se mantiene al crear la orden (día de la reserva), al reprogramar a otro día (se mueve el cupo) y queda
null cuando el cupo se libera (orden cancelada o parada saltada). Las órdenes existentes se rellenan con
el día de su reserva si sigue confirmada.

Escrita sin conexión a la BD (no ejecutada aún).

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d5e6f7a8b9c"
down_revision: Union[str, None] = "3c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("reserved_date", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE orders AS o
        SET reserved_date = h.date
        FROM holds AS h
        WHERE o.hold_id = h.id AND h.status = 'confirmed'
        """
    )


def downgrade() -> None:
    op.drop_column("orders", "reserved_date")
