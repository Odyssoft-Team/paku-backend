"""add description to store products and addons

Revision ID: a1b2c3d4e5f6
Revises: d1e2f3a4b5c6
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('store_products', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('store_addons', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('store_addons', 'description')
    op.drop_column('store_products', 'description')
