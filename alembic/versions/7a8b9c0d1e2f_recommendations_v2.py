"""Motor de recomendaciones del documento de precios V2 (feature 0008)

- recommendation_rules: reglas de servicio (hoja 17) y de adicionales (hoja 19), versión PAKU-REC-V1.
  Se cambian en la BD sin tocar código (p. ej. desactivar REC-005 o cambiar un texto).
- store_products.code y store_addons.code / requires_photo / duration_extra_min (hoja 18). Se cargan los
  códigos de los servicios y adicionales actuales por su nombre comercial.
- orders.review_status / review_note / reviewed_at: revisión previa del admin (manto muy apelmazado).

Escrita sin conexión a la BD (no ejecutada aún).

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
Create Date: 2026-10-15
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, None] = "6f7a8b9c0d1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VERSION = "PAKU-REC-V1"
WET = ["Clásico", "Medicado", "Premium"]
NO_SKIN = {"skin_sensitive": False}

_PRODUCT_CODES = {"Fresco y Limpio": "Clásico", "Cuidado Especial": "Medicado", "Spa Deluxe": "Premium",
                  "Express sin agua": "Seco"}
# nombre → (código, requiere foto)
_ADDON_CODES = {
    "Deslanado intensivo": ("ADD_DESLANADO_INT", False),
    "Desmotado localizado": ("ADD_DESMOTADO_LOC", False),
    "Desmotado extendido": ("ADD_DESMOTADO_EXT", True),
    "Corte estético": ("ADD_CORTE_EST", True),
    "Retoque Paku": ("ADD_RETOQUE", False),
    "Cepillo dental personal": ("ADD_TOOTHBRUSH", False),
}

# (id, kind, prioridad, acción, condiciones, código destino, requiere foto, texto)
_RULES = [
    ("REC-001", "service", 1, "RECOMENDAR", {"min_age_months": 0, "max_age_months": 4, "max_weight_kg": 10}, "Seco", False,
     "Por su edad y peso, recomendamos una limpieza suave sin agua, pensada para cachorros pequeños."),
    ("REC-002", "service", 2, "RECOMENDAR", {"skin_sensitive": True}, "Medicado", False,
     "Por la sensibilidad de su piel, recomendamos Cuidado Especial para usar productos compatibles con su condición."),
    ("REC-003", "service", 3, "RECOMENDAR", {"min_age_months": 5, "segments": ["S5"], **NO_SKIN}, "Premium", False,
     "Por su manto largo y denso, Spa Deluxe ayuda a mantener hidratación, suavidad y un mejor acabado."),
    ("REC-004", "service", 3, "RECOMENDAR", {"min_age_months": 5, "segments": ["S6"], **NO_SKIN}, "Premium", False,
     "Por la complejidad de su manto mixto o rizado denso, recomendamos un cuidado más completo."),
    ("REC-005", "service", 3, "RECOMENDAR", {"min_age_months": 5, "segments": ["S3"], **NO_SKIN}, "Premium", False,
     "Por su pelaje rizado o lanoso, recomendamos un servicio de mayor cuidado para facilitar el mantenimiento del manto."),
    ("REC-006", "service", 9, "RECOMENDAR", {"min_age_months": 5, "segments": ["S1"], **NO_SKIN}, "Clásico", False,
     "Para su tipo de pelaje y una rutina de higiene regular, Fresco y Limpio es una opción completa."),
    ("REC-007", "service", 9, "RECOMENDAR", {"min_age_months": 5, "segments": ["S2"], **NO_SKIN}, "Clásico", False,
     "Para su tipo de pelaje y mantenimiento habitual, recomendamos Fresco y Limpio."),
    ("REC-008", "service", 9, "RECOMENDAR", {"min_age_months": 5, "segments": ["S4"], **NO_SKIN}, "Clásico", False,
     "Para su manto y mantenimiento habitual, recomendamos Fresco y Limpio. El manejo normal de subpelo ya está considerado."),
    ("REC-999", "service", 99, "RECOMENDAR", {"fallback": True}, "Clásico", False,
     "Recomendamos Fresco y Limpio como opción de mantenimiento general."),
    ("AR-001", "addon", 1, "OCULTAR_ADICIONALES_SERVICIO", {"services": ["Seco"], "keep": ["ADD_TOOTHBRUSH"]}, None, False,
     "Para Express sin agua solo se mostrarán adicionales compatibles con este servicio."),
    ("AR-010", "addon", 10, "RECOMENDAR",
     {"services": WET, "segments": ["S4", "S5"], "question": "Q-SHEDDING", "answer": "HIGH"}, "ADD_DESLANADO_INT", False,
     "Por la muda intensa que indicaste, te recomendamos Deslanado intensivo."),
    ("AR-020", "addon", 10, "RECOMENDAR",
     {"services": WET, "segments": ["S2", "S3", "S5", "S6"], "question": "Q-MATTING", "answer": "LOCALIZED"},
     "ADD_DESMOTADO_LOC", False, "Como indicaste algunos nudos puntuales, te recomendamos Desmotado localizado."),
    ("AR-021", "addon", 10, "RECOMENDAR",
     {"services": WET, "segments": ["S2", "S3", "S5", "S6"], "question": "Q-MATTING", "answer": "EXTENDED"},
     "ADD_DESMOTADO_EXT", True,
     "Como indicaste nudos en varias zonas, te recomendamos Desmotado extendido y necesitaremos fotos antes de confirmar."),
    ("AR-022", "addon", 2, "REVISION_MANUAL",
     {"services": WET, "segments": ["S2", "S3", "S5", "S6"], "question": "Q-MATTING", "answer": "SEVERE"}, None, True,
     "El estado del manto requiere una revisión previa para confirmar que el servicio pueda realizarse de forma segura."),
    ("AR-030", "addon", 10, "RECOMENDAR",
     {"services": WET, "segments": ["S2", "S3", "S6"], "question": "Q-STYLING", "answer": "FULL_CUT"}, "ADD_CORTE_EST", True,
     "Si deseas un cambio de estilo completo, puedes agregar Corte estético."),
    ("AR-031", "addon", 10, "RECOMENDAR",
     {"services": WET, "segments": ["S2", "S3", "S6"], "max_weight_kg": 25, "question": "Q-STYLING", "answer": "RETOUCH"},
     "ADD_RETOQUE", False, "Si solo deseas mejorar carita, patas y cola, puedes elegir Retoque Paku."),
    ("AR-032", "addon", 3, "NO_DISPONIBLE",
     {"services": WET, "segments": ["S2", "S3", "S6"], "min_weight_kg": 25.01, "question": "Q-STYLING", "answer": "RETOUCH"},
     "ADD_RETOQUE", False, "El retoque para este rango de peso todavía no está disponible para compra."),
    ("AR-040", "addon", 20, "OFRECER", {"question": "Q-TOOTHBRUSH", "answer": "NO"}, "ADD_TOOTHBRUSH", False,
     "¿No tienes cepillo dental personal? Puedes agregar uno a tu reserva."),
]


def upgrade() -> None:
    op.add_column("store_products", sa.Column("code", sa.String(50), nullable=True))
    op.create_index("ix_store_products_code", "store_products", ["code"])
    op.add_column("store_addons", sa.Column("code", sa.String(50), nullable=True))
    op.create_index("ix_store_addons_code", "store_addons", ["code"])
    op.add_column("store_addons", sa.Column("requires_photo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("store_addons", sa.Column("duration_extra_min", sa.Integer(), nullable=True))

    op.add_column("orders", sa.Column("review_status", sa.String(20), nullable=True))
    op.create_index("ix_orders_review_status", "orders", ["review_status"])
    op.add_column("orders", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    rules = op.create_table(
        "recommendation_rules",
        sa.Column("id", sa.String(30), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("target_code", sa.String(50), nullable=True),
        sa.Column("requires_photo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(rules, [
        {"id": rid, "kind": kind, "priority": prio, "is_active": True, "action": action, "conditions": cond,
         "target_code": target, "requires_photo": photo, "text": text, "version": VERSION, "updated_at": now}
        for rid, kind, prio, action, cond, target, photo, text in _RULES
    ])

    conn = op.get_bind()
    for name, code in _PRODUCT_CODES.items():
        conn.execute(sa.text("UPDATE store_products SET code = CAST(:c AS VARCHAR) WHERE name = CAST(:n AS VARCHAR)"),
                     {"c": code, "n": name})
    for name, (code, photo) in _ADDON_CODES.items():
        conn.execute(
            sa.text("UPDATE store_addons SET code = CAST(:c AS VARCHAR), requires_photo = :p WHERE name = CAST(:n AS VARCHAR)"),
            {"c": code, "p": photo, "n": name},
        )


def downgrade() -> None:
    op.drop_table("recommendation_rules")
    op.drop_index("ix_orders_review_status", table_name="orders")
    for col in ("reviewed_at", "review_note", "review_status"):
        op.drop_column("orders", col)
    op.drop_index("ix_store_addons_code", table_name="store_addons")
    for col in ("duration_extra_min", "requires_photo", "code"):
        op.drop_column("store_addons", col)
    op.drop_index("ix_store_products_code", table_name="store_products")
    op.drop_column("store_products", "code")
