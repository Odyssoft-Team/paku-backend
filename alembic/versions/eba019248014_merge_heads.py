"""merge heads

Revision ID: eba019248014
Revises: a1b2c3d4e5f6, cf01dde0409a
Create Date: 2026-02-07 23:59:36.880336

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eba019248014'
down_revision = ('a1b2c3d4e5f6', 'cf01dde0409a')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
