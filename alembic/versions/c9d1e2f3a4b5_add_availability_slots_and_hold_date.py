"""add availability_slots table and holds.date column

Revision ID: c9d1e2f3a4b5
Revises: b7b6c5d4e3f2, eba019248014
Create Date: 2026-02-28

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c9d1e2f3a4b5'
down_revision = ('b7b6c5d4e3f2', 'eba019248014')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add date column to holds (nullable — existing rows won't have a date)
    op.add_column(
        'holds',
        sa.Column('date', sa.Date(), nullable=True),
    )
    op.create_index('ix_holds_date', 'holds', ['date'])

    # Create availability_slots table
    op.create_table(
        'availability_slots',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('service_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('booked', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_availability_slots_service_id', 'availability_slots', ['service_id'])
    op.create_index('ix_availability_slots_date', 'availability_slots', ['date'])
    op.create_unique_constraint(
        'uq_availability_service_date',
        'availability_slots',
        ['service_id', 'date'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_availability_service_date', 'availability_slots', type_='unique')
    op.drop_index('ix_availability_slots_date', table_name='availability_slots')
    op.drop_index('ix_availability_slots_service_id', table_name='availability_slots')
    op.drop_table('availability_slots')

    op.drop_index('ix_holds_date', table_name='holds')
    op.drop_column('holds', 'date')
