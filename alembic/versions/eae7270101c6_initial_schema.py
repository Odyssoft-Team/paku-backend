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
    # Create users table (IAM)
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('sex', sa.String(length=10), nullable=False),
        sa.Column('birth_date', sa.Date(), nullable=False),
        sa.Column('dni', sa.String(length=30), nullable=True),
        sa.Column('address_district_id', sa.String(length=50), nullable=True),
        sa.Column('address_line', sa.String(length=255), nullable=True),
        sa.Column('address_lat', sa.Float(), nullable=True),
        sa.Column('address_lng', sa.Float(), nullable=True),
        sa.Column('profile_photo_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

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

        # Nuevos campos
        sa.Column('sterilized', sa.Boolean(), nullable=True),
        sa.Column('size', sa.String(length=20), nullable=True),
        sa.Column('activity_level', sa.String(length=20), nullable=True),
        sa.Column('coat_type', sa.String(length=20), nullable=True),
        sa.Column('skin_sensitivity', sa.Boolean(), nullable=True),
        sa.Column('bath_behavior', sa.String(length=20), nullable=True),
        sa.Column('tolerates_drying', sa.Boolean(), nullable=True),
        sa.Column('tolerates_nail_clipping', sa.Boolean(), nullable=True),
        sa.Column('vaccines_up_to_date', sa.Boolean(), nullable=True),
        sa.Column('grooming_frequency', sa.String(length=100), nullable=True),
        sa.Column('receive_reminders', sa.Boolean(), nullable=True),
        sa.Column('antiparasitic', sa.Boolean(), nullable=True),
        sa.Column('antiparasitic_interval', sa.String(length=20), nullable=True),
        sa.Column('special_shampoo', sa.Boolean(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create pet_weight_entries table
    op.create_table(
        'pet_weight_entries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('pet_id', sa.Uuid(), nullable=False),
        sa.Column('weight_kg', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create services table (Commerce)
    op.create_table(
        'services',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('species', sa.String(length=20), nullable=False),
        sa.Column('allowed_breeds', sa.JSON(), nullable=True),
        sa.Column('requires', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create price_rules table (Commerce)
    op.create_table(
        'price_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('service_id', sa.Uuid(), nullable=False),
        sa.Column('species', sa.String(length=20), nullable=False),
        sa.Column('breed_category', sa.String(length=30), nullable=False),
        sa.Column('weight_min', sa.Float(), nullable=False),
        sa.Column('weight_max', sa.Float(), nullable=True),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create holds table (Booking)
    op.create_table(
        'holds',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('pet_id', sa.Uuid(), nullable=False),
        sa.Column('service_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('quote_snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('items_snapshot', sa.JSON(), nullable=False),
        sa.Column('total_snapshot', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('delivery_address_snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create device_tokens table (Push)
    op.create_table(
        'device_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create cart_sessions table (Cart)
    op.create_table(
        'cart_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create cart_items table (Cart)
    op.create_table(
        'cart_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('cart_id', sa.Uuid(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('ref_id', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('cart_items')
    op.drop_table('cart_sessions')
    op.drop_table('device_tokens')
    op.drop_table('notifications')
    op.drop_table('orders')
    op.drop_table('holds')
    op.drop_table('price_rules')
    op.drop_table('services')
    op.drop_table('pet_weight_entries')
    op.drop_table('pets')
    op.drop_table('users')
