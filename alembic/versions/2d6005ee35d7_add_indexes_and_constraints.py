"""add indexes and constraints

Revision ID: 2d6005ee35d7
Revises: 7073a500860c
Create Date: 2026-01-24 00:37:54.887325

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d6005ee35d7'
down_revision = '7073a500860c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # iam users: unique email
    try:
        op.create_unique_constraint('uq_users_email', 'users', ['email'])
    except Exception:
        pass

    # pets: index owner_id
    try:
        op.create_index('ix_pets_owner_id', 'pets', ['owner_id'])
    except Exception:
        pass

    # pets weight history: index (pet_id, recorded_at DESC)
    try:
        op.create_index('ix_pet_weight_entries_pet_recorded', 'pet_weight_entries', ['pet_id', 'recorded_at'])
    except Exception:
        pass

    # commerce services: index (species, is_active)
    try:
        op.create_index('ix_services_species_active', 'services', ['species', 'is_active'])
    except Exception:
        pass

    # commerce price_rules: index (service_id, species, is_active)
    try:
        op.create_index('ix_price_rules_service_species_active', 'price_rules', ['service_id', 'species', 'is_active'])
    except Exception:
        pass

    # commerce price_rules: index (weight_min, weight_max)
    try:
        op.create_index('ix_price_rules_weight_range', 'price_rules', ['weight_min', 'weight_max'])
    except Exception:
        pass

    # booking holds: index (user_id, status)
    try:
        op.create_index('ix_holds_user_status', 'holds', ['user_id', 'status'])
    except Exception:
        pass

    # booking holds: index expires_at
    try:
        op.create_index('ix_holds_expires_at', 'holds', ['expires_at'])
    except Exception:
        pass

    # orders: index (user_id, created_at DESC)
    try:
        op.create_index('ix_orders_user_created_desc', 'orders', ['user_id', sa.text('created_at DESC')])
    except Exception:
        pass

    # orders: index status
    try:
        op.create_index('ix_orders_status', 'orders', ['status'])
    except Exception:
        pass

    # notifications: index (user_id, is_read, created_at DESC)
    try:
        op.create_index('ix_notifications_user_read_created_desc', 'notifications', ['user_id', 'is_read', sa.text('created_at DESC')])
    except Exception:
        pass

    # notifications: index created_at
    try:
        op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
    except Exception:
        pass

    # push device_tokens: unique (user_id, platform, token)
    try:
        op.create_unique_constraint('uq_device_tokens_user_platform_token', 'device_tokens', ['user_id', 'platform', 'token'])
    except Exception:
        pass

    # push device_tokens: index (user_id, is_active)
    try:
        op.create_index('ix_device_tokens_user_active', 'device_tokens', ['user_id', 'is_active'])
    except Exception:
        pass

    # cart sessions: index (user_id, status)
    try:
        op.create_index('ix_cart_sessions_user_status', 'cart_sessions', ['user_id', 'status'])
    except Exception:
        pass

    # cart sessions: index expires_at
    try:
        op.create_index('ix_cart_sessions_expires_at', 'cart_sessions', ['expires_at'])
    except Exception:
        pass

    # cart items: index cart_id
    try:
        op.create_index('ix_cart_items_cart_id', 'cart_items', ['cart_id'])
    except Exception:
        pass


def downgrade() -> None:
    # cart items: drop index cart_id
    try:
        op.drop_index('ix_cart_items_cart_id', 'cart_items')
    except Exception:
        pass

    # cart sessions: drop expires_at
    try:
        op.drop_index('ix_cart_sessions_expires_at', 'cart_sessions')
    except Exception:
        pass

    # cart sessions: drop (user_id, status)
    try:
        op.drop_index('ix_cart_sessions_user_status', 'cart_sessions')
    except Exception:
        pass

    # push device_tokens: drop (user_id, is_active)
    try:
        op.drop_index('ix_device_tokens_user_active', 'device_tokens')
    except Exception:
        pass

    # push device_tokens: drop unique (user_id, platform, token)
    try:
        op.drop_constraint('uq_device_tokens_user_platform_token', 'device_tokens', type_='unique')
    except Exception:
        pass

    # notifications: drop created_at
    try:
        op.drop_index('ix_notifications_created_at', 'notifications')
    except Exception:
        pass

    # notifications: drop (user_id, is_read, created_at DESC)
    try:
        op.drop_index('ix_notifications_user_read_created_desc', 'notifications')
    except Exception:
        pass

    # orders: drop status
    try:
        op.drop_index('ix_orders_status', 'orders')
    except Exception:
        pass

    # orders: drop (user_id, created_at DESC)
    try:
        op.drop_index('ix_orders_user_created_desc', 'orders')
    except Exception:
        pass

    # booking holds: drop expires_at
    try:
        op.drop_index('ix_holds_expires_at', 'holds')
    except Exception:
        pass

    # booking holds: drop (user_id, status)
    try:
        op.drop_index('ix_holds_user_status', 'holds')
    except Exception:
        pass

    # commerce price_rules: drop (weight_min, weight_max)
    try:
        op.drop_index('ix_price_rules_weight_range', 'price_rules')
    except Exception:
        pass

    # commerce price_rules: drop (service_id, species, is_active)
    try:
        op.drop_index('ix_price_rules_service_species_active', 'price_rules')
    except Exception:
        pass

    # commerce services: drop (species, is_active)
    try:
        op.drop_index('ix_services_species_active', 'services')
    except Exception:
        pass

    # pets weight history: drop (pet_id, recorded_at)
    try:
        op.drop_index('ix_pet_weight_entries_pet_recorded', 'pet_weight_entries')
    except Exception:
        pass

    # pets: drop owner_id
    try:
        op.drop_index('ix_pets_owner_id', 'pets')
    except Exception:
        pass

    # iam users: drop unique email
    try:
        op.drop_constraint('uq_users_email', 'users', type_='unique')
    except Exception:
        pass
