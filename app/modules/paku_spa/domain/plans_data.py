"""Hardcoded Paku Spa plans.

Constraints:
- No DB, no ORM models, no migrations.
- Keep response stable for frontend consumption.
"""

from __future__ import annotations

from typing import Final


PLANS: Final[list[dict]] = [
    {
        "code": "classic",
        "name": "Clásico",
        "description": "Cuidado esencial para el día a día",
        "price": 80,
        "currency": "PEN",
        "includes": [
            "Limpieza completa y segura",
            "Cuidado básico de uñas y oídos",
            "Brillo y frescura inmediata",
        ],
    },
    {
        "code": "premium",
        "name": "Premium",
        "description": "Experiencia spa de alto nivel",
        "price": 89,
        "currency": "PEN",
        "includes": [
            "Hidratación profunda del pelaje",
            "Mascarilla nutritiva y acabado superior",
            "Suavidad y brillo prolongado",
        ],
    },
    {
        "code": "express",
        "name": "Express / Seco",
        "description": "Limpieza rápida sin agua",
        "price": 75,
        "currency": "PEN",
        "includes": [
            "Shampoo en seco hipoalergénico",
            "Ideal entre baños o para cachorros hasta los 4 meses",
            "Frescura inmediata",
        ],
    },
]
