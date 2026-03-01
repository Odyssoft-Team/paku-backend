"""add missing tables: cart_sessions, cart_items, notifications, device_tokens

Revision ID: c6d7e8f9a0b1
Revises: e3f4a5b6c7d8
Create Date: 2026-03-01

"""

from alembic import op
import sqlalchemy as sa


revision = 'c6d7e8f9a0b1'
down_revision = 'e3f4a5b6c7d8'
branch_labels = None
depends_on = None

# Para crear los tipos con checkfirst (no falla si ya existen)
_cartstatus_create = sa.Enum('active', 'checked_out', 'expired', 'cancelled', name='cartstatus')
_platform_create   = sa.Enum('android', 'ios', 'web', name='platform')

# Para usar en create_table sin que SQLAlchemy intente crearlos de nuevo
cartstatus_enum = sa.Enum('active', 'checked_out', 'expired', 'cancelled', name='cartstatus', create_type=False)
platform_enum   = sa.Enum('android', 'ios', 'web', name='platform', create_type=False)


def upgrade() -> None:
    _cartstatus_create.create(op.get_bind(), checkfirst=True)
    _platform_create.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'cart_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('status', cartstatus_enum, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cart_sessions_user_id', 'cart_sessions', ['user_id'])
    op.create_index('ix_cart_sessions_expires', 'cart_sessions', ['expires_at'])
    op.create_index('ix_cart_sessions_user_status', 'cart_sessions', ['user_id', 'status'])

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
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cart_items_cart_id', 'cart_items', ['cart_id'])
    op.create_index('ix_cart_items_kind_ref', 'cart_items', ['kind', 'ref_id'])

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
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
    op.create_index('ix_notifications_user_created', 'notifications', ['user_id', 'created_at'])
    op.create_index('ix_notifications_user_unread', 'notifications', ['user_id', 'is_read'])

    op.create_table(
        'device_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('platform', platform_enum, nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_device_tokens_user_id', 'device_tokens', ['user_id'])
    op.create_index('ix_device_tokens_token', 'device_tokens', ['token'])
    op.create_index('ix_device_tokens_is_active', 'device_tokens', ['is_active'])
    op.create_index('ix_device_tokens_user_active', 'device_tokens', ['user_id', 'is_active'])
    op.create_index(
        'ix_device_tokens_user_platform_token',
        'device_tokens',
        ['user_id', 'platform', 'token'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_device_tokens_user_platform_token', table_name='device_tokens')
    op.drop_index('ix_device_tokens_user_active', table_name='device_tokens')
    op.drop_index('ix_device_tokens_is_active', table_name='device_tokens')
    op.drop_index('ix_device_tokens_token', table_name='device_tokens')
    op.drop_index('ix_device_tokens_user_id', table_name='device_tokens')
    op.drop_table('device_tokens')

    op.drop_index('ix_notifications_user_unread', table_name='notifications')
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')

    op.drop_index('ix_cart_items_kind_ref', table_name='cart_items')
    op.drop_index('ix_cart_items_cart_id', table_name='cart_items')
    op.drop_table('cart_items')

    op.drop_index('ix_cart_sessions_user_status', table_name='cart_sessions')
    op.drop_index('ix_cart_sessions_expires', table_name='cart_sessions')
    op.drop_index('ix_cart_sessions_user_id', table_name='cart_sessions')
    op.drop_table('cart_sessions')

    platform_enum.drop(op.get_bind(), checkfirst=True)
    cartstatus_enum.drop(op.get_bind(), checkfirst=True)
