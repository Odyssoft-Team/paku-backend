"""renombra ally → groomer (rol, columnas, tabla de tracking y datos)

El término de dominio pasa a ser "groomer" (groomers contratados por Paku). Cambia:
  - users.role: 'ally' → 'groomer'
  - chat_messages.sender_role: 'ally' → 'groomer'
  - pet_records.recorded_by_role: 'ally' → 'groomer'
  - orders.ally_id → orders.groomer_id (+ índice)
  - order_assignments.ally_id → order_assignments.groomer_id (+ índice)
  - ally_locations → groomer_locations, ally_id → groomer_id (+ índice)

Solo renombra: no borra ni recalcula datos. Escrita sin conexión a la BD (no ejecutada aún).

Revision ID: 1a2b3c4d5e6f
Revises: fb7c8d9e0f1a
Create Date: 2026-10-03
"""
from typing import Sequence, Union

from alembic import op


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "fb7c8d9e0f1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Datos: valores de rol guardados como texto
    op.execute("UPDATE users SET role = 'groomer' WHERE role = 'ally'")
    op.execute("UPDATE chat_messages SET sender_role = 'groomer' WHERE sender_role = 'ally'")
    op.execute("UPDATE pet_records SET recorded_by_role = 'groomer' WHERE recorded_by_role = 'ally'")

    # orders
    op.alter_column("orders", "ally_id", new_column_name="groomer_id")
    # IF EXISTS: un índice con otro nombre en alguna BD no debe impedir el arranque (el renombre es cosmético).
    op.execute("ALTER INDEX IF EXISTS ix_orders_ally_id RENAME TO ix_orders_groomer_id")

    # order_assignments
    op.alter_column("order_assignments", "ally_id", new_column_name="groomer_id")
    op.execute("ALTER INDEX IF EXISTS ix_order_assignments_ally_id RENAME TO ix_order_assignments_groomer_id")

    # tracking
    op.rename_table("ally_locations", "groomer_locations")
    op.alter_column("groomer_locations", "ally_id", new_column_name="groomer_id")
    op.execute("ALTER INDEX IF EXISTS ix_ally_locations_ally_id RENAME TO ix_groomer_locations_groomer_id")


def downgrade() -> None:
    op.execute("ALTER INDEX IF EXISTS ix_groomer_locations_groomer_id RENAME TO ix_ally_locations_ally_id")
    op.alter_column("groomer_locations", "groomer_id", new_column_name="ally_id")
    op.rename_table("groomer_locations", "ally_locations")

    op.execute("ALTER INDEX IF EXISTS ix_order_assignments_groomer_id RENAME TO ix_order_assignments_ally_id")
    op.alter_column("order_assignments", "groomer_id", new_column_name="ally_id")

    op.execute("ALTER INDEX IF EXISTS ix_orders_groomer_id RENAME TO ix_orders_ally_id")
    op.alter_column("orders", "groomer_id", new_column_name="ally_id")

    op.execute("UPDATE pet_records SET recorded_by_role = 'ally' WHERE recorded_by_role = 'groomer'")
    op.execute("UPDATE chat_messages SET sender_role = 'ally' WHERE sender_role = 'groomer'")
    op.execute("UPDATE users SET role = 'ally' WHERE role = 'groomer'")
