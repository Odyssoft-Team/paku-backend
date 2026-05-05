"""initial schema consolidado

Revision ID: 0000000000000
Revises:
Create Date: 2026-05-05

Migración inicial limpia que crea el esquema completo del proyecto según los
modelos SQLAlchemy actuales. Reemplaza la cadena histórica de 9 migraciones.

Para usar esta migración como punto de partida en un entorno nuevo:
  1. Asegúrate de que la BD esté vacía (sin tablas).
  2. Ejecuta: alembic upgrade 0000000000000
  3. (Opcional) Marcar como head: alembic stamp 0000000000000

Tablas incluidas (19):
  IAM:          users, user_addresses, user_social_identities
  Pets:         pets, pet_weight_entries, pet_records
  Booking:      holds, availability_slots
  Orders:       orders, order_assignments
  Cart:         cart_sessions, cart_items
  Notifications: notifications
  Push:         device_tokens
  Catalog:      breeds
  Store:        store_categories, store_products, store_addons, store_price_rules

Enums PostgreSQL: cartstatus, platform
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0000000000000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# UPGRADE
# ---------------------------------------------------------------------------

def upgrade() -> None:

    # ------------------------------------------------------------------
    # ENUMS
    # ------------------------------------------------------------------
    op.execute("DROP TYPE IF EXISTS cartstatus")
    op.execute("DROP TYPE IF EXISTS platform")

    # ------------------------------------------------------------------
    # TABLA: users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("sex", sa.String(10), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("profile_completed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("dni", sa.String(30), nullable=True),
        sa.Column("address_district_id", sa.String(50), nullable=True),
        sa.Column("address_line", sa.String(255), nullable=True),
        sa.Column("address_lat", sa.Float(), nullable=True),
        sa.Column("address_lng", sa.Float(), nullable=True),
        sa.Column("profile_photo_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # TABLA: user_addresses
    # ------------------------------------------------------------------
    op.create_table(
        "user_addresses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("district_id", sa.String(20), nullable=False),
        sa.Column("address_line", sa.String(255), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("building_number", sa.String(50), nullable=True),
        sa.Column("apartment_number", sa.String(50), nullable=True),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_user_addresses_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_addresses_user_id", "user_addresses", ["user_id"])
    op.create_index("ix_user_addresses_user_default", "user_addresses", ["user_id", "is_default"])
    op.create_index("ix_user_addresses_user_deleted", "user_addresses", ["user_id", "deleted_at"])

    # ------------------------------------------------------------------
    # TABLA: user_social_identities
    # ------------------------------------------------------------------
    op.create_table(
        "user_social_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("firebase_uid", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_user_social_identities_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("firebase_uid", name="uq_user_social_identities_firebase_uid"),
    )
    op.create_index("ix_user_social_identities_user_id", "user_social_identities", ["user_id"])

    # ------------------------------------------------------------------
    # TABLA: pets
    # ------------------------------------------------------------------
    op.create_table(
        "pets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("species", sa.String(20), nullable=False),
        sa.Column("breed", sa.String(100), nullable=True),
        sa.Column("sex", sa.String(10), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("sterilized", sa.Boolean(), nullable=True),
        sa.Column("size", sa.String(20), nullable=True),
        sa.Column("activity_level", sa.String(20), nullable=True),
        sa.Column("coat_type", sa.String(20), nullable=True),
        sa.Column("skin_sensitivity", sa.Boolean(), nullable=True),
        sa.Column("bath_behavior", sa.String(20), nullable=True),
        sa.Column("tolerates_drying", sa.Boolean(), nullable=True),
        sa.Column("tolerates_nail_clipping", sa.Boolean(), nullable=True),
        sa.Column("vaccines_up_to_date", sa.Boolean(), nullable=True),
        sa.Column("grooming_frequency", sa.String(100), nullable=True),
        sa.Column("receive_reminders", sa.Boolean(), nullable=True),
        sa.Column("antiparasitic", sa.Boolean(), nullable=True),
        sa.Column("antiparasitic_interval", sa.String(20), nullable=True),
        sa.Column("special_shampoo", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pets_owner_id"), "pets", ["owner_id"])

    # ------------------------------------------------------------------
    # TABLA: pet_weight_entries
    # ------------------------------------------------------------------
    op.create_table(
        "pet_weight_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["pet_id"], ["pets.id"],
            name="fk_pet_weight_entries_pet_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pet_weight_entries_pet_id"), "pet_weight_entries", ["pet_id"])

    # ------------------------------------------------------------------
    # TABLA: pet_records
    # ------------------------------------------------------------------
    op.create_table(
        "pet_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_by_role", sa.String(20), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("attachment_ids", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["pet_id"], ["pets.id"],
            name="fk_pet_records_pet_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pet_records_pet_id"), "pet_records", ["pet_id"])
    op.create_index(op.f("ix_pet_records_type"), "pet_records", ["type"])
    op.create_index(op.f("ix_pet_records_occurred_at"), "pet_records", ["occurred_at"])
    op.create_index("ix_pet_records_pet_id_type", "pet_records", ["pet_id", "type"])
    op.create_index("ix_pet_records_pet_id_occurred_at", "pet_records", ["pet_id", "occurred_at"])

    # ------------------------------------------------------------------
    # TABLA: holds
    # ------------------------------------------------------------------
    op.create_table(
        "holds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("quote_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_holds_user_id"), "holds", ["user_id"])
    op.create_index(op.f("ix_holds_pet_id"), "holds", ["pet_id"])
    op.create_index(op.f("ix_holds_expires_at"), "holds", ["expires_at"])
    op.create_index(op.f("ix_holds_date"), "holds", ["date"])

    # ------------------------------------------------------------------
    # TABLA: availability_slots
    # ------------------------------------------------------------------
    op.create_table(
        "availability_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("booked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_id", "date", name="uq_availability_service_date"),
    )
    op.create_index(op.f("ix_availability_slots_service_id"), "availability_slots", ["service_id"])
    op.create_index(op.f("ix_availability_slots_date"), "availability_slots", ["date"])

    # ------------------------------------------------------------------
    # TABLA: orders
    # ------------------------------------------------------------------
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="created"),
        sa.Column("items_snapshot", sa.JSON(), nullable=False),
        sa.Column("total_snapshot", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="PEN"),
        sa.Column("delivery_address_snapshot", sa.JSON(), nullable=True),
        sa.Column("ally_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hold_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"])
    op.create_index(op.f("ix_orders_ally_id"), "orders", ["ally_id"])

    # ------------------------------------------------------------------
    # TABLA: order_assignments
    # ------------------------------------------------------------------
    op.create_table(
        "order_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("ally_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"],
            name="fk_order_assignments_order_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_assignments_order_id"), "order_assignments", ["order_id"])
    op.create_index(op.f("ix_order_assignments_ally_id"), "order_assignments", ["ally_id"])

    # ------------------------------------------------------------------
    # TABLA: cart_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "cart_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "checked_out", "expired", "cancelled", name="cartstatus"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Nota: expires_at tiene index=True en la columna (→ ix_cart_sessions_expires_at)
    # Y Index("ix_cart_sessions_expires") en __table_args__. Ambos existen en el modelo.
    # La migración crea los dos para ser fiel al estado actual del modelo.
    op.create_index(op.f("ix_cart_sessions_user_id"), "cart_sessions", ["user_id"])
    op.create_index(op.f("ix_cart_sessions_expires_at"), "cart_sessions", ["expires_at"])
    op.create_index("ix_cart_sessions_expires", "cart_sessions", ["expires_at"])
    op.create_index("ix_cart_sessions_user_status", "cart_sessions", ["user_id", "status"])

    # ------------------------------------------------------------------
    # TABLA: cart_items
    # ------------------------------------------------------------------
    op.create_table(
        "cart_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cart_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("ref_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Nota: cart_id tiene index=True en la columna Y Index("ix_cart_items_cart_id") en
    # __table_args__ con el mismo nombre. SQLAlchemy deduplica → un solo índice.
    op.create_index("ix_cart_items_cart_id", "cart_items", ["cart_id"])
    op.create_index("ix_cart_items_kind_ref", "cart_items", ["kind", "ref_id"])

    # ------------------------------------------------------------------
    # TABLA: notifications
    # ------------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"])
    op.create_index(op.f("ix_notifications_is_read"), "notifications", ["is_read"])
    op.create_index(op.f("ix_notifications_created_at"), "notifications", ["created_at"])
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "is_read"])

    # ------------------------------------------------------------------
    # TABLA: device_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("android", "ios", "web", name="platform"),
            nullable=False,
        ),
        sa.Column("token", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_tokens_user_id"), "device_tokens", ["user_id"])
    op.create_index(op.f("ix_device_tokens_token"), "device_tokens", ["token"])
    op.create_index(op.f("ix_device_tokens_is_active"), "device_tokens", ["is_active"])
    op.create_index("ix_device_tokens_user_active", "device_tokens", ["user_id", "is_active"])
    op.create_index(
        "ix_device_tokens_user_platform_token",
        "device_tokens",
        ["user_id", "platform", "token"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # TABLA: breeds
    # ------------------------------------------------------------------
    op.create_table(
        "breeds",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("species", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("coat_group", sa.String(20), nullable=True),
        sa.Column("coat_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_breeds_species", "breeds", ["species"])
    op.create_index("ix_breeds_species_active", "breeds", ["species", "is_active"])

    # ------------------------------------------------------------------
    # TABLA: store_categories
    # ------------------------------------------------------------------
    op.create_table(
        "store_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("species", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # unique=True refleja mapped_column(unique=True, index=True) en CategoryModel.
    # Sin UniqueConstraint separado: evita tener dos objetos de unicidad sobre slug
    # y garantiza que autogenerate no detecte drift.
    op.create_index("ix_store_categories_slug", "store_categories", ["slug"], unique=True)

    # ------------------------------------------------------------------
    # TABLA: store_products
    # ------------------------------------------------------------------
    op.create_table(
        "store_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("species", sa.String(20), nullable=False),
        sa.Column("allowed_breeds", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"], ["store_categories.id"],
            name="fk_store_products_category_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_store_products_category_id", "store_products", ["category_id"])

    # ------------------------------------------------------------------
    # TABLA: store_addons
    # ------------------------------------------------------------------
    op.create_table(
        "store_addons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("species", sa.String(20), nullable=False),
        sa.Column("allowed_breeds", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["store_products.id"],
            name="fk_store_addons_product_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_store_addons_product_id", "store_addons", ["product_id"])

    # ------------------------------------------------------------------
    # TABLA: store_price_rules
    # ------------------------------------------------------------------
    op.create_table(
        "store_price_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("species", sa.String(20), nullable=False),
        sa.Column("breed_category", sa.String(30), nullable=False),
        sa.Column("weight_min", sa.Float(), nullable=False),
        sa.Column("weight_max", sa.Float(), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="PEN"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_store_price_rules_target_id", "store_price_rules", ["target_id"])
    op.create_index(
        "ix_store_price_rules_lookup",
        "store_price_rules",
        ["target_id", "target_type", "species", "breed_category"],
    )


# ---------------------------------------------------------------------------
# DOWNGRADE
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Tablas en orden inverso de dependencia
    op.drop_index("ix_store_price_rules_lookup", table_name="store_price_rules")
    op.drop_index("ix_store_price_rules_target_id", table_name="store_price_rules")
    op.drop_table("store_price_rules")

    op.drop_index("ix_store_addons_product_id", table_name="store_addons")
    op.drop_table("store_addons")

    op.drop_index("ix_store_products_category_id", table_name="store_products")
    op.drop_table("store_products")

    op.drop_index("ix_store_categories_slug", table_name="store_categories")
    op.drop_table("store_categories")

    op.drop_index("ix_breeds_species_active", table_name="breeds")
    op.drop_index("ix_breeds_species", table_name="breeds")
    op.drop_table("breeds")

    op.drop_index("ix_device_tokens_user_platform_token", table_name="device_tokens")
    op.drop_index("ix_device_tokens_user_active", table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_is_active"), table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_token"), table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_user_id"), table_name="device_tokens")
    op.drop_table("device_tokens")

    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_is_read"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_cart_items_kind_ref", table_name="cart_items")
    op.drop_index("ix_cart_items_cart_id", table_name="cart_items")
    op.drop_table("cart_items")

    op.drop_index("ix_cart_sessions_user_status", table_name="cart_sessions")
    op.drop_index("ix_cart_sessions_expires", table_name="cart_sessions")
    op.drop_index(op.f("ix_cart_sessions_expires_at"), table_name="cart_sessions")
    op.drop_index(op.f("ix_cart_sessions_user_id"), table_name="cart_sessions")
    op.drop_table("cart_sessions")

    op.drop_index(op.f("ix_order_assignments_ally_id"), table_name="order_assignments")
    op.drop_index(op.f("ix_order_assignments_order_id"), table_name="order_assignments")
    op.drop_table("order_assignments")

    op.drop_index(op.f("ix_orders_ally_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_user_id"), table_name="orders")
    op.drop_table("orders")

    op.drop_index(op.f("ix_availability_slots_date"), table_name="availability_slots")
    op.drop_index(op.f("ix_availability_slots_service_id"), table_name="availability_slots")
    op.drop_table("availability_slots")

    op.drop_index(op.f("ix_holds_date"), table_name="holds")
    op.drop_index(op.f("ix_holds_expires_at"), table_name="holds")
    op.drop_index(op.f("ix_holds_pet_id"), table_name="holds")
    op.drop_index(op.f("ix_holds_user_id"), table_name="holds")
    op.drop_table("holds")

    op.drop_index("ix_pet_records_pet_id_occurred_at", table_name="pet_records")
    op.drop_index("ix_pet_records_pet_id_type", table_name="pet_records")
    op.drop_index(op.f("ix_pet_records_occurred_at"), table_name="pet_records")
    op.drop_index(op.f("ix_pet_records_type"), table_name="pet_records")
    op.drop_index(op.f("ix_pet_records_pet_id"), table_name="pet_records")
    op.drop_table("pet_records")

    op.drop_index(op.f("ix_pet_weight_entries_pet_id"), table_name="pet_weight_entries")
    op.drop_table("pet_weight_entries")

    op.drop_index(op.f("ix_pets_owner_id"), table_name="pets")
    op.drop_table("pets")

    op.drop_index("ix_user_social_identities_user_id", table_name="user_social_identities")
    op.drop_table("user_social_identities")

    op.drop_index("ix_user_addresses_user_deleted", table_name="user_addresses")
    op.drop_index("ix_user_addresses_user_default", table_name="user_addresses")
    op.drop_index("ix_user_addresses_user_id", table_name="user_addresses")
    op.drop_table("user_addresses")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS platform")
    op.execute("DROP TYPE IF EXISTS cartstatus")
