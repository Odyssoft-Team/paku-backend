"""Categoría de precio de una mascota (feature 0004, precios por tipo de pelaje).

El precio de un servicio o addon depende de especie, categoría de precio y peso
(ver `StorePriceRuleModel`). La categoría de precio es:

- El **tipo de pelaje** de la raza del catálogo (6 tipos, `breeds_data.coat_type`),
  porque el pelaje define el trabajo del groomer.
- **"mestizo"** para mestizos, razas escritas a mano, sin raza o razas sin tipo de
  pelaje (p. ej. gatos). Es también el respaldo: si un producto no tiene precio
  para un pelaje, se cotiza con su fila "mestizo".

Antes (2026-09-04 → 0004) se cotizaba por "official"/"otros"/"mestizo" y las reglas
por pelaje cargadas en el admin no se usaban. "official"/"otros" quedan como
categorías antiguas: ya no se crean y el admin las muestra para desactivarlas.
"""

from __future__ import annotations

from typing import Optional

from app.modules.catalog.domain.breeds_data import BREEDS_CATALOG

FALLBACK_CATEGORY = "mestizo"

# Orden de presentación en el admin (filas de la tabla de precios)
PRICE_CATEGORIES: list[tuple[str, str]] = [
    ("simple_short", "Pelo corto sin subpelo"),
    ("simple_medium_long", "Pelo medio/largo sin subpelo"),
    ("curly_no_undercoat", "Rizado sin subpelo"),
    ("double_short", "Doble manto corto"),
    ("double_long", "Doble manto largo"),
    ("mixed_curly_undercoat", "Mixto/rizado con subpelo"),
    (FALLBACK_CATEGORY, "Mestizo u otra raza"),
]
VALID_PRICE_CATEGORIES = {key for key, _ in PRICE_CATEGORIES}

# Categorías del esquema anterior: ya no se usan al cotizar
LEGACY_PRICE_CATEGORIES = {"official", "otros"}

# Tramos de peso sugeridos para la tabla del admin (kg). El último no tiene tope.
DEFAULT_WEIGHT_TIERS: list[tuple[float, Optional[float]]] = [
    (0, 5),
    (5.01, 15),
    (15.01, 25),
    (25.01, 35),
    (35.01, 50),
    (50.01, None),
]

_COAT_BY_BREED: dict[str, Optional[str]] = {
    breed["id"]: breed.get("coat_type")
    for group in BREEDS_CATALOG
    for breed in group["breeds"]
}


def price_category(breed_id: Optional[str], breed_name: Optional[str] = None) -> str:
    """Categoría de precio de la mascota: pelaje de su raza del catálogo o "mestizo".

    `breed_name` se acepta por compatibilidad con los llamadores: una raza escrita a
    mano (sin `breed_id`) no tiene pelaje conocido y se cotiza como "mestizo".
    """
    if breed_id:
        coat = _COAT_BY_BREED.get(breed_id.strip().lower())
        if coat in VALID_PRICE_CATEGORIES:
            return coat
    return FALLBACK_CATEGORY


def category_label(category: str) -> str:
    for key, label in PRICE_CATEGORIES:
        if key == category:
            return label
    if category in LEGACY_PRICE_CATEGORIES:
        return f"{category} (antigua, no se usa)"
    return category
