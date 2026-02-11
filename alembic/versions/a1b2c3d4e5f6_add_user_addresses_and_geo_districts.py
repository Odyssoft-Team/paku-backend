"""add_user_addresses

Revision ID: a1b2c3d4e5f6
Revises: eae7270101c6
Create Date: 2026-02-07 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'eae7270101c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_addresses table
    op.create_table(
        'user_addresses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('district_id', sa.String(length=20), nullable=False),
        sa.Column('address_line', sa.String(length=255), nullable=False),
        sa.Column('reference', sa.Text(), nullable=True),
        sa.Column('building_number', sa.String(length=50), nullable=True),
        sa.Column('apartment_number', sa.String(length=50), nullable=True),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lng', sa.Float(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for user_addresses
    op.create_index(op.f('ix_user_addresses_user_id'), 'user_addresses', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_addresses_district_id'), 'user_addresses', ['district_id'], unique=False)
    op.create_index('ix_user_addresses_user_default', 'user_addresses', ['user_id', 'is_default'], unique=False)
    op.create_index('ix_user_addresses_user_deleted', 'user_addresses', ['user_id', 'deleted_at'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_user_addresses_user_deleted', table_name='user_addresses')
    op.drop_index('ix_user_addresses_user_default', table_name='user_addresses')
    op.drop_index(op.f('ix_user_addresses_district_id'), table_name='user_addresses')
    op.drop_index(op.f('ix_user_addresses_user_id'), table_name='user_addresses')

    # Drop tables
    op.drop_table('user_addresses')
