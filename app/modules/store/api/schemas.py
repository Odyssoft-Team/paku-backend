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


class ProductUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    allowed_breeds: Optional[List[str]] = None


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
