"""Rango de precios por tamaño (feature 0009): el registro de mascota ya no pide el peso, sino el tamaño
(uno por tramo de precio) y muestra cuánto cuesta cada uno para esa raza.

Para cada tramo de `DEFAULT_WEIGHT_TIERS`: mínimo y máximo de los servicios activos de la categoría que
no tienen requisitos de edad o peso (Express sin agua, solo cachorros, no representa al resto).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException

from app.modules.store.domain.models import Species
from app.modules.store.domain.pricing import DEFAULT_WEIGHT_TIERS


@dataclass
class PriceRange:
    weight_min: float
    weight_max: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]


async def price_ranges(repo, *, category_slug: str, species: Species, breed_id: Optional[str]) -> list[PriceRange]:
    category = await repo.get_category_by_slug(category_slug)
    if not category or not category.is_active:
        raise HTTPException(status_code=404, detail="Category not found")
    breed_category = await repo.price_category_for(breed_id)
    products = [
        p for p in await repo.list_products(category_id=category.id, species=species)
        if p.is_active and p.max_weight_kg is None and p.max_age_months is None
    ]
    out: list[PriceRange] = []
    for lo, hi in DEFAULT_WEIGHT_TIERS:
        weight = hi if hi is not None else lo + 5  # un peso dentro del tramo
        prices = [
            price for p in products
            if (price := await repo.price_for(target_id=p.id, target_type="product", species=species,
                                              breed_category=breed_category, weight=weight)) is not None
        ]
        out.append(PriceRange(weight_min=lo, weight_max=hi,
                              min_price=min(prices) if prices else None,
                              max_price=max(prices) if prices else None))
    return out
