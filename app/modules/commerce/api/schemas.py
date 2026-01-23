from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

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
