"""check

Revision ID: 7073a500860c
Revises: eae7270101c6
Create Date: 2026-01-23 22:29:38.052684
"""

from alembic import op
import sqlalchemy as sa

revision = '7073a500860c'
down_revision = 'eae7270101c6'
branch_labels = None
depends_on = None


""" def upgrade() -> None:
    op.create_table(
        'pets',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('owner_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('species', sa.String(), nullable=False),
        sa.Column('breed', sa.String(), nullable=True),
        sa.Column('sex', sa.String(), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('microchip', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('pets') """

def upgrade() -> None:
    # Placeholder migration - tables created in initial_schema
    pass
def downgrade() -> None:
    # Placeholder migration - tables dropped in initial_schema
    pass