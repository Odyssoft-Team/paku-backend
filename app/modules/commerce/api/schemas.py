from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.commerce.domain.service import ServiceType, Species


# [TECH] DTO de salida de Service. Expone campos del catálogo (tipo/especie/reglas). Output: JSON.
# [NEGOCIO] Estructura que la app usa para mostrar un servicio disponible.
class ServiceOut(BaseModel):
    id: UUID
    name: str
    type: ServiceType
    species: Species
    allowed_breeds: Optional[List[str]]
    requires: Optional[List[UUID]]
    is_active: bool


# [TECH] DTO de salida de servicios disponibles por mascota. Incluye addons filtrados.
# [NEGOCIO] Lista qué servicios y adicionales aplican para una mascota específica.
class ServiceAvailableOut(ServiceOut):
    available_addons: List[ServiceOut]


# [TECH] DTO de entrada para cotización. Inputs: pet_id, base_service_id, addon_ids. Output: validación.
# [NEGOCIO] Datos que se envían para saber cuánto costará un servicio con opcionales.
class QuoteIn(BaseModel):
    pet_id: UUID
    base_service_id: UUID
    addon_ids: Optional[List[UUID]] = None


# [TECH] Línea de cotización (servicio + precio). Output: desglose para UI.
# [NEGOCIO] Muestra cada parte del precio para que el cliente entienda el total.
class QuoteLineOut(BaseModel):
    service_id: UUID
    name: str
    price: int


# [TECH] DTO de salida de cotización. Output: base + addons + total + moneda.
# [NEGOCIO] Resultado final del precio a cobrar por el servicio seleccionado.
class QuoteOut(BaseModel):
    pet_id: UUID
    base: QuoteLineOut
    addons: List[QuoteLineOut]
    total: int
    currency: str = "PEN"


# ------------------------------------------------------------------
# Admin schemas
# ------------------------------------------------------------------

class ServiceCreateIn(BaseModel):
    name: str
    type: ServiceType
    species: Species
    allowed_breeds: Optional[List[str]] = None
    requires: Optional[List[UUID]] = None
    is_active: bool = True


class ServiceUpdateIn(BaseModel):
    name: Optional[str] = None
    allowed_breeds: Optional[List[str]] = None
    requires: Optional[List[UUID]] = None


class ServiceToggleIn(BaseModel):
    is_active: bool


class PriceRuleOut(BaseModel):
    id: UUID
    service_id: UUID
    species: Species
    breed_category: str
    weight_min: float
    weight_max: Optional[float]
    price: int
    currency: str
    is_active: bool


class PriceRuleCreateIn(BaseModel):
    service_id: UUID
    species: Species
    breed_category: str
    weight_min: float = Field(ge=0)
    weight_max: Optional[float] = None
    price: int = Field(ge=0)
    currency: str = "PEN"


class PriceRuleUpdateIn(BaseModel):
    price: Optional[int] = Field(default=None, ge=0)
    weight_min: Optional[float] = Field(default=None, ge=0)
    weight_max: Optional[float] = None
    is_active: Optional[bool] = None
