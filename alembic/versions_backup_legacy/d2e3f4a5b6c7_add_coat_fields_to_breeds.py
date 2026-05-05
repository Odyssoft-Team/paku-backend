"""catalog: add coat_group and coat_type to breeds

Revision ID: d2e3f4a5b6c7
Revises: c2d3e4f5a6b7
Create Date: 2026-03-21

Agrega coat_group ("single" | "double") y coat_type (6 valores finos)
a la tabla breeds. Columnas nullable: los valores se poblarán cuando
se ejecute el seed con breeds_data.py actualizado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("breeds", sa.Column("coat_group", sa.String(20), nullable=True))
    op.add_column("breeds", sa.Column("coat_type", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("breeds", "coat_type")
    op.drop_column("breeds", "coat_group")
