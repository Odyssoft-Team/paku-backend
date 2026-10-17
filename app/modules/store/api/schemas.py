from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.store.domain.models import Species


# ------------------------------------------------------------------
# Salida pública
# ------------------------------------------------------------------

class CategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    species: Optional[Species]
    is_active: bool


class ProductOut(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    description: Optional[str]
    species: Species
    allowed_breeds: Optional[List[str]]
    is_active: bool
    price: Optional[float] = None   # soles con decimales, ej: 120.0
    currency: str = "PEN"
    included_items: Optional[List[str]] = None
    max_weight_kg: Optional[float] = None   # requisito de la mascota; null = sin límite
    max_age_months: Optional[int] = None    # requisito de la mascota; null = sin límite
    code: Optional[str] = None              # Clásico | Medicado | Premium | Seco (0008)


class AddonOut(BaseModel):
    id: UUID
    product_id: UUID
    name: str
    description: Optional[str]
    species: Species
    allowed_breeds: Optional[List[str]]
    is_active: bool
    price: Optional[float] = None   # soles con decimales, ej: 15.0
    currency: str = "PEN"
    code: Optional[str] = None                 # ADD_DESLANADO_INT… (hoja 18, 0008)
    requires_photo: bool = False               # el cliente sube fotos antes de pagar
    duration_extra_min: Optional[int] = None   # pendiente del negocio


class ProductDetailOut(ProductOut):
    available_addons: List[AddonOut]


class QuoteLineOut(BaseModel):
    target_id: UUID
    name: str
    price: float   # soles con decimales, ej: 120.0


class QuoteOut(BaseModel):
    pet_id: UUID
    product: QuoteLineOut
    addons: List[QuoteLineOut]
    total: float   # soles con decimales
    currency: str = "PEN"


# ------------------------------------------------------------------
# Entrada pública
# ------------------------------------------------------------------

class QuoteIn(BaseModel):
    pet_id: UUID
    product_id: UUID
    addon_ids: Optional[List[UUID]] = None


# ------------------------------------------------------------------
# Admin — categorías
# ------------------------------------------------------------------

class CategoryCreateIn(BaseModel):
    name: str
    slug: str
    species: Optional[Species] = None
    is_active: bool = True


class CategoryUpdateIn(BaseModel):
    name: Optional[str] = None
    species: Optional[Species] = None


class ToggleIn(BaseModel):
    is_active: bool


# ------------------------------------------------------------------
# Admin — productos
# ------------------------------------------------------------------

class ProductCreateIn(BaseModel):
    category_id: UUID
    name: str
    description: Optional[str] = None
    species: Species
    allowed_breeds: Optional[List[str]] = None
    is_active: bool = True
    included_items: Optional[List[str]] = None
    max_weight_kg: Optional[float] = None
    max_age_months: Optional[int] = None


class ProductUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    allowed_breeds: Optional[List[str]] = None
    included_items: Optional[List[str]] = None
    # Enviar null quita el límite; omitir el campo lo deja como está.
    max_weight_kg: Optional[float] = None
    max_age_months: Optional[int] = None
    code: Optional[str] = None


# ------------------------------------------------------------------
# Admin — addons
# ------------------------------------------------------------------

class AddonCreateIn(BaseModel):
    product_id: UUID
    name: str
    description: Optional[str] = None
    species: Species
    allowed_breeds: Optional[List[str]] = None
    is_active: bool = True


class AddonUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    allowed_breeds: Optional[List[str]] = None
    # Catálogo (0008): solo cambia lo enviado
    code: Optional[str] = None
    requires_photo: Optional[bool] = None
    duration_extra_min: Optional[int] = None


# ------------------------------------------------------------------
# Admin — price rules
# ------------------------------------------------------------------

class PriceRuleOut(BaseModel):
    id: UUID
    target_id: UUID
    target_type: str
    species: Species
    breed_category: str
    weight_min: float
    weight_max: Optional[float]
    price: float   # soles con decimales, ej: 120.0
    currency: str
    is_active: bool


class PriceRuleCreateIn(BaseModel):
    target_id: UUID
    target_type: str          # "product" | "addon"
    species: Species
    breed_category: str
    weight_min: float = Field(ge=0)
    weight_max: Optional[float] = Field(default=None, ge=0)
    price: float = Field(ge=0)   # soles con decimales, ej: 120.0
    currency: str = "PEN"


class PriceRuleUpdateIn(BaseModel):
    price: Optional[float] = Field(default=None, ge=0)   # soles con decimales
    weight_min: Optional[float] = Field(default=None, ge=0)
    weight_max: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


# ------------------------------------------------------------------
# Tabla de precios (feature 0004)
# ------------------------------------------------------------------

class PriceMatrixCellIn(BaseModel):
    breed_category: str        # tipo de pelaje o "mestizo" (GET /admin/store/price-config)
    weight_min: float = Field(ge=0)
    weight_max: Optional[float] = Field(default=None, ge=0)   # null = sin tope
    price: float = Field(ge=0)   # soles con decimales


class PriceMatrixIn(BaseModel):
    target_type: str           # "product" | "addon"
    cells: List[PriceMatrixCellIn]
    currency: str = "PEN"


class PriceCategoryOut(BaseModel):
    key: str
    label: str


class WeightTierOut(BaseModel):
    weight_min: float
    weight_max: Optional[float]


class PriceConfigOut(BaseModel):
    categories: List[PriceCategoryOut]
    fallback_category: str
    weight_tiers: List[WeightTierOut]


class SimulatedPriceOut(BaseModel):
    id: UUID
    name: str
    price: Optional[float]           # null = sin precio: no se puede comprar
    category_used: Optional[str]     # categoría de la regla aplicada
    used_fallback: bool              # true = se usó la fila "mestizo" por falta del pelaje


class SimulatedProductOut(SimulatedPriceOut):
    addons: List[SimulatedPriceOut]


class PriceSimulationOut(BaseModel):
    price_category: str
    price_category_label: str
    products: List[SimulatedProductOut]


# ------------------------------------------------------------------
# Recomendaciones (feature 0008)
# ------------------------------------------------------------------

class RecommendationIn(BaseModel):
    pet_id: UUID
    product_id: Optional[UUID] = None          # con servicio elegido: también evalúa sus adicionales
    answers: Optional[dict[str, str]] = None   # {"Q-MATTING": "LOCALIZED", …}


class QuestionOptionOut(BaseModel):
    code: str
    label: str


class QuestionOut(BaseModel):
    id: str
    text: str
    options: List[QuestionOptionOut]
    required: bool


class RecommendedServiceOut(BaseModel):
    product_id: UUID
    code: Optional[str]
    name: str
    rule_id: str
    text: Optional[str]


class AddonRecommendationOut(BaseModel):
    addon_id: UUID
    code: Optional[str]
    name: str
    price: Optional[float]
    action: Optional[str]        # RECOMENDAR | OFRECER | null (disponible)
    rule_id: Optional[str]
    text: Optional[str]
    requires_photo: bool


class ReviewOut(BaseModel):
    rule_id: str
    text: Optional[str]
    requires_photo: bool


class RecommendationOut(BaseModel):
    version: str
    segment: Optional[str]
    service: Optional[RecommendedServiceOut]
    questions: List[QuestionOut]
    addons: List[AddonRecommendationOut]
    review: Optional[ReviewOut]


class PriceRangeOut(BaseModel):
    """Rango de precio de un tramo de peso (tamaño) para una raza (feature 0009)."""
    weight_min: float
    weight_max: Optional[float]   # null = sin tope (último tramo)
    min_price: Optional[float]
    max_price: Optional[float]
