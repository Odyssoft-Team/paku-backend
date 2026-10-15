"""Reglas del documento de precios del cliente (features 0005 y 0006)

store_products (0005):
- max_weight_kg / max_age_months: peso y edad máximos para reservar el servicio (null = sin límite).
  Ej.: Express sin agua → 10 kg y 4 meses. Se configuran desde el admin.

breeds (0006): el admin asigna el pelaje de cada raza (define el precio).
- Columnas is_mixed, photo_url, description.
- Mestizos: 6 razas nuevas (dog_mixed_1..6), una por pelaje, que el cliente elige por foto.
  "dog_mixed" queda inactiva (mascotas antiguas siguen cotizando con la fila "mestizo").
- Variantes de pelo: Dachshund, Chihuahua, Pastor Alemán, Chow Chow y Cocker en corto y largo.
- Pug → doble manto corto, Pekinés → doble manto largo, Cocker (corte corto) → pelo medio/largo.
- Nuevas: Lagotto Romagnolo, Perro de Agua Portugués, Aussiedoodle.
  La tabla solo se siembra si está vacía, por eso se actualiza aquí (mismo contenido que
  app/modules/catalog/domain/breeds_data.py).

pets (0006):
- weight_updated_at: último cambio de peso (el dueño espera 30 días para el siguiente).
- reactive, bite_history, muzzle_required, fragrance: seguridad y preferencia de perfume.

Escrita sin conexión a la BD (no ejecutada aún).

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-10-14
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f7a8b9c0d1e"
down_revision: Union[str, None] = "5e6f7a8b9c0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (id, nombre, coat_group, coat_type) de razas existentes que cambian
_UPDATED = [
    ("pug", "Pug", "double", "double_short"),
    ("pekines", "Pekinés", "double", "double_long"),
    ("dachshund", "Dachshund (Salchicha) pelo corto", "single", "simple_short"),
    ("chihuahua", "Chihuahua pelo corto", "single", "simple_short"),
    ("pastor_aleman", "Pastor Alemán pelo corto", "double", "double_short"),
    ("chow_chow", "Chow Chow pelo corto", "double", "double_short"),
    ("cocker_spaniel", "Cocker Spaniel corte corto", "single", "simple_medium_long"),
]
# Valores anteriores, para el downgrade
_PREVIOUS = {
    "pug": ("Pug", "single", "simple_short"),
    "pekines": ("Pekinés", "single", "simple_medium_long"),
    "dachshund": ("Dachshund (Salchicha)", "single", "simple_short"),
    "chihuahua": ("Chihuahua", "single", "simple_short"),
    "pastor_aleman": ("Pastor Alemán", "double", "double_short"),
    "chow_chow": ("Chow Chow", "double", "double_short"),
    "cocker_spaniel": ("Cocker Spaniel", "double", "double_short"),
}
# (id, nombre, coat_group, coat_type, is_mixed, descripción)
_NEW = [
    ("lagotto_romagnolo", "Lagotto Romagnolo", "single", "curly_no_undercoat", False, None),
    ("perro_agua_portugues", "Perro de Agua Portugués", "single", "curly_no_undercoat", False, None),
    ("aussiedoodle", "Aussiedoodle", "double", "mixed_curly_undercoat", False, None),
    ("dachshund_largo", "Dachshund (Salchicha) pelo largo", "single", "simple_medium_long", False, None),
    ("chihuahua_largo", "Chihuahua pelo largo", "single", "simple_medium_long", False, None),
    ("pastor_aleman_largo", "Pastor Alemán pelo largo", "double", "double_long", False, None),
    ("chow_chow_largo", "Chow Chow pelo largo", "double", "double_long", False, None),
    ("cocker_spaniel_largo", "Cocker Spaniel manto largo", "double", "double_long", False, None),
    ("dog_mixed_1", "Mestizo 1 · Pelo corto", "single", "simple_short", True,
     "Pelo corto y pegado al cuerpo."),
    ("dog_mixed_2", "Mestizo 2 · Pelo medio o largo", "single", "simple_medium_long", True,
     "Pelo liso o sedoso, de largo medio a largo, sin subpelo."),
    ("dog_mixed_3", "Mestizo 3 · Pelo rizado", "single", "curly_no_undercoat", True,
     "Pelo rizado o lanoso que crece continuamente."),
    ("dog_mixed_4", "Mestizo 4 · Doble manto corto", "double", "double_short", True,
     "Pelo corto y denso con mucho subpelo; muda bastante."),
    ("dog_mixed_5", "Mestizo 5 · Doble manto largo", "double", "double_long", True,
     "Pelo largo y muy denso con mucho subpelo."),
    ("dog_mixed_6", "Mestizo 6 · Mixto o rizado denso", "double", "mixed_curly_undercoat", True,
     "Mezcla de rizo y subpelo, muy denso."),
]


def upgrade() -> None:
    op.add_column("store_products", sa.Column("max_weight_kg", sa.Float(), nullable=True))
    op.add_column("store_products", sa.Column("max_age_months", sa.Integer(), nullable=True))

    op.add_column("breeds", sa.Column("is_mixed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("breeds", sa.Column("photo_url", sa.Text(), nullable=True))
    op.add_column("breeds", sa.Column("description", sa.Text(), nullable=True))

    op.add_column("pets", sa.Column("weight_updated_at", sa.DateTime(timezone=True), nullable=True))
    for col in ("reactive", "bite_history", "muzzle_required", "fragrance"):
        op.add_column("pets", sa.Column(col, sa.Boolean(), nullable=True))

    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    for breed_id, name, group, coat in _UPDATED:
        conn.execute(
            sa.text("UPDATE breeds SET name = :n, coat_group = :g, coat_type = :c, updated_at = :now WHERE id = :id"),
            {"n": name, "g": group, "c": coat, "now": now, "id": breed_id},
        )
    for breed_id, name, group, coat, mixed, desc in _NEW:
        conn.execute(
            sa.text(
                "INSERT INTO breeds (id, name, species, is_active, coat_group, coat_type, is_mixed, description, "
                "created_at, updated_at) "
                "SELECT :id, :name, 'dog', true, :g, :c, :m, :d, :now, :now "
                "WHERE NOT EXISTS (SELECT 1 FROM breeds WHERE id = :id)"
            ),
            {"id": breed_id, "name": name, "g": group, "c": coat, "m": mixed, "d": desc, "now": now},
        )
    # El "Mestizo" genérico ya no se elige: el cliente elige uno de los 6 por foto
    conn.execute(sa.text("UPDATE breeds SET is_active = false, updated_at = :now WHERE id = 'dog_mixed'"), {"now": now})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE breeds SET is_active = true WHERE id = 'dog_mixed'"))
    for breed_id, *_ in _NEW:
        conn.execute(sa.text("DELETE FROM breeds WHERE id = :id"), {"id": breed_id})
    for breed_id, (name, group, coat) in _PREVIOUS.items():
        conn.execute(
            sa.text("UPDATE breeds SET name = :n, coat_group = :g, coat_type = :c WHERE id = :id"),
            {"n": name, "g": group, "c": coat, "id": breed_id},
        )
    for col in ("fragrance", "muzzle_required", "bite_history", "reactive", "weight_updated_at"):
        op.drop_column("pets", col)
    for col in ("description", "photo_url", "is_mixed"):
        op.drop_column("breeds", col)
    op.drop_column("store_products", "max_age_months")
    op.drop_column("store_products", "max_weight_kg")
