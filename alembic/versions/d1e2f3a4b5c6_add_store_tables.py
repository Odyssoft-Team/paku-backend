"""add store tables

Revision ID: d1e2f3a4b5c6
Revises: c6d7e8f9a0b1
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'd1e2f3a4b5c6'
down_revision = 'c6d7e8f9a0b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'store_categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('species', sa.String(20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_store_categories_slug', 'store_categories', ['slug'], unique=True)

    op.create_table(
        'store_products',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('store_categories.id'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('species', sa.String(20), nullable=False),
        sa.Column('allowed_breeds', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_store_products_category_id', 'store_products', ['category_id'])

    op.create_table(
        'store_addons',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('product_id', UUID(as_uuid=True), sa.ForeignKey('store_products.id'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('species', sa.String(20), nullable=False),
        sa.Column('allowed_breeds', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_store_addons_product_id', 'store_addons', ['product_id'])

    op.create_table(
        'store_price_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('target_id', UUID(as_uuid=True), nullable=False),
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('species', sa.String(20), nullable=False),
        sa.Column('breed_category', sa.String(30), nullable=False),
        sa.Column('weight_min', sa.Float(), nullable=False),
        sa.Column('weight_max', sa.Float(), nullable=True),
        sa.Column('price', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False, server_default='PEN'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_store_price_rules_target_id', 'store_price_rules', ['target_id'])


def downgrade() -> None:
    op.drop_table('store_price_rules')
    op.drop_table('store_addons')
    op.drop_table('store_products')
    op.drop_table('store_categories')
