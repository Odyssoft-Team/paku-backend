"""remove_geo_districts_and_fk

Revision ID: b7b6c5d4e3f2
Revises: a1b2c3d4e5f6
Create Date: 2026-02-11

NOTE: This migration is intentionally a no-op.

During early development, the Geo catalog was moved to hardcoded data and the
`geo_districts` table + foreign key were removed from the migration that
introduced `user_addresses`.

If you are resetting the database (dropping it and re-running `alembic upgrade head`),
there is nothing to do here.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "b7b6c5d4e3f2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op (see module docstring)
    pass


def downgrade() -> None:
    # No-op
    pass
