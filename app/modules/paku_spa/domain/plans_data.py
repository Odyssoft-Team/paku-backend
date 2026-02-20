"""Hardcoded Paku Spa plans.

Constraints:
- No DB, no ORM models, no migrations.
- Keep response stable for frontend consumption.
- UUIDs are fixed for cart/order compatibility (will migrate to commerce/services later).
"""

from __future__ import annotations

from typing import Final


PLANS: Final[list[dict]] = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440001",  # UUID fijo para cart/orders
        "code": "classic",
        "name": "Clásico",
        "description": "Cuidado esencial para el día a día",
        "price": 80.0,
        "currency": "PEN",
        "includes": [
            "Limpieza completa y segura",
            "Cuidado básico de uñas y oídos",
            "Brillo y frescura inmediata",
        ],
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440002",  # UUID fijo para cart/orders
        "code": "premium",
        "name": "Premium",
        "description": "Experiencia spa de alto nivel",
        "price": 89.0,
        "currency": "PEN",
        "includes": [
            "Hidratación profunda del pelaje",
            "Mascarilla nutritiva y acabado superior",
            "Suavidad y brillo prolongado",
        ],
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440003",  # UUID fijo para cart/orders
        "code": "express",
        "name": "Express / Seco",
        "description": "Limpieza rápida sin agua",
        "price": 75.0,
        "currency": "PEN",
        "includes": [
            "Shampoo en seco hipoalergénico",
            "Ideal entre baños o para cachorros hasta los 4 meses",
            "Frescura inmediata",
        ],
    },
]
