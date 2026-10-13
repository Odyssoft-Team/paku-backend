"""Gestión de precios del admin (feature 0004): tabla completa, simulador y configuración."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.store.domain.models import PriceRule, Species, breed_allowed
from app.modules.store.domain.pricing import (
    DEFAULT_WEIGHT_TIERS,
    FALLBACK_CATEGORY,
    PRICE_CATEGORIES,
    VALID_PRICE_CATEGORIES,
    category_label,
    price_category,
)
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository


def _error(code: str, message: str, **extra) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": code, "message": message, **extra},
    )


def validate_matrix(cells: list[dict]) -> None:
    """Categorías válidas, precios no negativos y tramos de peso sin solaparse por categoría."""
    by_category: dict[str, list[dict]] = {}
    for c in cells:
        if c["breed_category"] not in VALID_PRICE_CATEGORIES:
            raise _error(
                "PRICE_CATEGORY_INVALID",
                f"Categoría desconocida: {c['breed_category']}.",
                valid=sorted(VALID_PRICE_CATEGORIES),
            )
        if c["price"] < 0:
            raise _error("PRICE_INVALID", "El precio no puede ser negativo.")
        if c["weight_min"] < 0 or (c["weight_max"] is not None and c["weight_max"] <= c["weight_min"]):
            raise _error(
                "WEIGHT_RANGE_INVALID",
                "Cada tramo debe tener un peso máximo mayor que el mínimo.",
                breed_category=c["breed_category"],
            )
        by_category.setdefault(c["breed_category"], []).append(c)

    for category, items in by_category.items():
        items = sorted(items, key=lambda x: x["weight_min"])
        for prev, cur in zip(items, items[1:]):
            if prev["weight_max"] is None or cur["weight_min"] <= prev["weight_max"]:
                raise _error(
                    "WEIGHT_RANGE_OVERLAP",
                    f"Los tramos de peso de «{category_label(category)}» se superponen.",
                    breed_category=category,
                )


@dataclass
class ReplacePriceMatrix:
    """PUT /admin/store/price-matrix/{target_id}: guarda la tabla completa de un producto o addon."""

    repo: PostgresStoreRepository

    async def execute(
        self,
        *,
        target_id: UUID,
        target_type: str,
        cells: list[dict],
        currency: str = "PEN",
    ) -> List[PriceRule]:
        if target_type == "product":
            target = await self.repo.get_product(target_id)
        elif target_type == "addon":
            target = await self.repo.get_addon(target_id)
        else:
            raise _error("TARGET_TYPE_INVALID", "target_type debe ser 'product' o 'addon'.")
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

        validate_matrix(cells)
        return await self.repo.replace_price_rules(
            target_id=target_id,
            target_type=target_type,
            species=target.species,
            rules=cells,
            currency=currency,
        )


@dataclass
class SimulatedPrice:
    id: UUID
    name: str
    price: Optional[float]
    category_used: Optional[str]
    used_fallback: bool


@dataclass
class SimulatedProduct(SimulatedPrice):
    addons: List[SimulatedPrice] = field(default_factory=list)


@dataclass
class SimulationResult:
    price_category: str
    price_category_label: str
    products: List[SimulatedProduct]


@dataclass
class SimulatePrices:
    """GET /admin/store/price-simulation: lo que pagaría una mascota (raza + peso) en una
    categoría de la tienda, con la misma lógica que la cotización real."""

    repo: PostgresStoreRepository

    async def execute(
        self,
        *,
        category_id: UUID,
        species: Species,
        weight: float,
        breed_id: Optional[str] = None,
        breed_name: Optional[str] = None,
    ) -> SimulationResult:
        if weight <= 0:
            raise _error("WEIGHT_INVALID", "El peso debe ser mayor que 0.")
        category = price_category(breed_id, breed_name)

        async def _price(target_id: UUID, target_type: str) -> tuple[Optional[float], Optional[str]]:
            return await self.repo.price_detail_for(
                target_id=target_id,
                target_type=target_type,
                species=species,
                breed_category=category,
                weight=weight,
            )

        products: List[SimulatedProduct] = []
        for p in await self.repo.list_products(category_id=category_id, species=species):
            if not breed_allowed(p.allowed_breeds, breed_id, breed_name):
                continue
            price, used = await _price(p.id, "product")
            item = SimulatedProduct(
                id=p.id,
                name=p.name,
                price=price,
                category_used=used,
                used_fallback=used is not None and used != category,
            )
            for a in await self.repo.list_addons(product_id=p.id):
                if a.species != species or not breed_allowed(a.allowed_breeds, breed_id, breed_name):
                    continue
                a_price, a_used = await _price(a.id, "addon")
                item.addons.append(
                    SimulatedPrice(
                        id=a.id,
                        name=a.name,
                        price=a_price,
                        category_used=a_used,
                        used_fallback=a_used is not None and a_used != category,
                    )
                )
            products.append(item)

        return SimulationResult(
            price_category=category,
            price_category_label=category_label(category),
            products=products,
        )


def pricing_config() -> dict:
    """GET /admin/store/price-config: filas (categorías) y tramos de peso sugeridos de la tabla."""
    return {
        "categories": [{"key": key, "label": label} for key, label in PRICE_CATEGORIES],
        "fallback_category": FALLBACK_CATEGORY,
        "weight_tiers": [{"weight_min": lo, "weight_max": hi} for lo, hi in DEFAULT_WEIGHT_TIERS],
    }
