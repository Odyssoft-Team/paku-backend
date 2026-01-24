"""fix cartstatus enum

Revision ID: e03bb2e74308
Revises: 2d6005ee35d7
Create Date: 2026-01-24 12:19:43.513433

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e03bb2e74308'
down_revision = '2d6005ee35d7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear el tipo ENUM cartstatus si no existe
    cartstatus_enum = sa.Enum('active', 'checked_out', 'expired', 'cancelled', name='cartstatus')
    cartstatus_enum.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # No eliminamos el ENUM para evitar errores si está en uso
    # Es más seguro dejarlo existir
    pass
