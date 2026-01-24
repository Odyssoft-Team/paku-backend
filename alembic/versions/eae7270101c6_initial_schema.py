"""initial schema

Revision ID: eae7270101c6
Revises:
Create Date: 2026-01-24 01:05:54.776190

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eae7270101c6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pets table
    op.create_table(
        'pets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('species', sa.String(length=20), nullable=False),
        sa.Column('breed', sa.String(length=100), nullable=True),
        sa.Column('sex', sa.String(length=10), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('photo_url', sa.String(length=500), nullable=True),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_pets_owner_id', 'owner_id')
    )

    # Create pet_weight_entries table
    op.create_table(
        'pet_weight_entries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('pet_id', sa.Uuid(), nullable=False),
        sa.Column('weight_kg', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_pet_weight_entries_pet_id', 'pet_id')
    )


def downgrade() -> None:
    op.drop_table('pet_weight_entries')
    op.drop_table('pets')
