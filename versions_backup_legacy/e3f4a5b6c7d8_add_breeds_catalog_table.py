"""add breeds catalog table

Revision ID: e3f4a5b6c7d8
Revises: f12c6b49c83e
Create Date: 2026-02-28

"""

from alembic import op
import sqlalchemy as sa


revision = 'e3f4a5b6c7d8'
down_revision = 'f12c6b49c83e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'breeds',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('species', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_breeds_species', 'breeds', ['species'])
    op.create_index('ix_breeds_species_active', 'breeds', ['species', 'is_active'])


def downgrade() -> None:
    op.drop_index('ix_breeds_species_active', table_name='breeds')
    op.drop_index('ix_breeds_species', table_name='breeds')
    op.drop_table('breeds')
