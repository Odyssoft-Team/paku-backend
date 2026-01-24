"""alter cart_sessions status to enum

Revision ID: cf01dde0409a
Revises: e03bb2e74308
Create Date: 2026-01-24 12:54:09.758072

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf01dde0409a'
down_revision = 'e03bb2e74308'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asegurar que el tipo ENUM cartstatus exista
    cartstatus_enum = sa.Enum('active', 'checked_out', 'expired', 'cancelled', name='cartstatus')
    cartstatus_enum.create(op.get_bind(), checkfirst=True)
    
    # Normalizar valores NULL si existen (establecer a 'active' por defecto)
    op.execute("UPDATE cart_sessions SET status = 'active' WHERE status IS NULL")
    
    # Convertir la columna status a ENUM cartstatus
    op.execute("""
        ALTER TABLE cart_sessions 
        ALTER COLUMN status TYPE cartstatus 
        USING status::cartstatus
    """)


def downgrade() -> None:
    # Convertir de vuelta a VARCHAR (conservador)
    op.execute("""
        ALTER TABLE cart_sessions 
        ALTER COLUMN status TYPE VARCHAR(20) 
        USING status::text
    """)
