"""users: índice único y formato de DNI (feature 0027, PAKU-USERS-009)

Obligatoria antes de producción. No modifica, elimina ni fusiona usuarios: si hay DNI inválidos o repetidos, se niega
a aplicarse y pide correr el diagnóstico (``python -m scripts.diagnostico_dni``) para corregirlos a mano.

- ``uq_users_dni``: índice único parcial (``dni IS NOT NULL``). Varias cuentas sin DNI siguen permitidas.
- ``ck_users_dni_formato``: el DNI es NULL o tiene 8 dígitos (lo mismo que valida la aplicación).

Revision ID: e8f3a1c7d5b2
Revises: d2e7f1a9c4b8
Create Date: 2026-11-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f3a1c7d5b2"
down_revision: Union[str, None] = "d2e7f1a9c4b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PATRON_DNI = "^[0-9]{8}$"
SQL_INVALIDOS = f"SELECT count(*) FROM users WHERE dni IS NOT NULL AND dni !~ '{PATRON_DNI}'"
SQL_DUPLICADOS = (
    "SELECT count(*) FROM (SELECT dni FROM users WHERE dni IS NOT NULL GROUP BY dni HAVING count(*) > 1) AS repetidos"
)


def verificar_datos(invalidos: int, duplicados: int) -> None:
    """Se niega a seguir si hay datos que romperían el índice o el CHECK. No corrige nada."""
    if invalidos or duplicados:
        raise RuntimeError(
            f"users.dni tiene {invalidos} valores con formato inválido y {duplicados} DNI repetidos. "
            "Corríjalos a mano (python -m scripts.diagnostico_dni) y vuelva a migrar. "
            "Esta migración no modifica, elimina ni fusiona usuarios."
        )


def upgrade() -> None:
    conexion = op.get_bind()
    verificar_datos(
        conexion.execute(sa.text(SQL_INVALIDOS)).scalar_one(),
        conexion.execute(sa.text(SQL_DUPLICADOS)).scalar_one(),
    )
    op.create_check_constraint("ck_users_dni_formato", "users", f"dni IS NULL OR dni ~ '{PATRON_DNI}'")
    op.create_index("uq_users_dni", "users", ["dni"], unique=True, postgresql_where=sa.text("dni IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_users_dni", table_name="users")
    op.drop_constraint("ck_users_dni_formato", "users", type_="check")
