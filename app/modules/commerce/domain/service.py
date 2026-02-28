from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4


# [TECH] Enum de tipo de servicio (base/addon). Define catálogo y reglas de addons.
# [NEGOCIO] Distingue entre el servicio principal y los adicionales que se pueden sumar.
class ServiceType(str, Enum):
    base = "base"
    addon = "addon"


# [TECH] Enum de especie (dog/cat). Filtra catálogo y precios por mascota.
# [NEGOCIO] Permite mostrar/usar servicios correctos según si es perro o gato.
class Species(str, Enum):
    dog = "dog"
    cat = "cat"


@dataclass(frozen=True)
# [TECH] Entidad Service del catálogo. Incluye visibilidad (is_active), especie, tipo y dependencias (requires).
# [NEGOCIO] Representa un servicio disponible para ofrecer y cobrar al cliente.
class Service:
    id: UUID
    name: str
    type: ServiceType
    species: Species
    allowed_breeds: Optional[List[str]]
    requires: Optional[List[UUID]]
    is_active: bool


@dataclass(frozen=True)
class PriceRule:
    id: UUID
    service_id: UUID
    species: Species
    breed_category: str
    weight_min: float
    weight_max: Optional[float]
    price: int
    currency: str
    is_active: bool
