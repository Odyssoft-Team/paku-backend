from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Config ──────────────────────────────────────────────────────────────────

class CodeLabelOut(BaseModel):
    code: str
    label: str


class InventoryConfigOut(BaseModel):
    categories: list[CodeLabelOut]
    consumption_units: list[str]
    movement_types: list[CodeLabelOut]
    manual_movement_types: list[str]      # los que se registran a mano (POST /movements)
    locations: list[str]
    cost_centers: list[CodeLabelOut]


# ─── Insumos ─────────────────────────────────────────────────────────────────

class SupplierIn(BaseModel):
    """Proveedor de un insumo. Solo el nombre es obligatorio; vacío = sin dato."""
    name: str = Field(min_length=1, max_length=200)
    product_code: Optional[str] = Field(default=None, max_length=60, description="Código del producto para el proveedor")
    phone: Optional[str] = Field(default=None, max_length=30)
    address: Optional[str] = Field(default=None, max_length=300)
    bank_account: Optional[str] = Field(default=None, max_length=100, description="Banco y número de cuenta / CCI")
    ruc: Optional[str] = Field(default=None, max_length=11, description="11 dígitos")


class SupplierOut(BaseModel):
    name: str
    product_code: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    bank_account: Optional[str] = None
    ruc: Optional[str] = None


class SupplyOut(BaseModel):
    id: UUID
    sku: str
    name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    suppliers: list[SupplierOut] = Field(default_factory=list)
    category: str
    category_label: str
    purchase_unit: str
    purchase_content: float
    consumption_unit: str
    purchase_cost: float
    unit_cost: float = Field(description="S/ por unidad de consumo (costo de compra ÷ contenido)")
    min_stock: float
    tracks_lot: bool
    tracks_expiry: bool
    is_active: bool
    stock: float = Field(description="Suma de los movimientos, en unidad de consumo")
    status: Literal["ok", "low", "out"]
    value: float = Field(description="max(stock, 0) × costo por unidad")
    created_at: datetime
    updated_at: datetime


class SupplyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    brand: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    suppliers: list[SupplierIn] = Field(default_factory=list)
    category: str
    purchase_unit: str = Field(min_length=1, max_length=50)
    purchase_content: float = Field(gt=0)
    consumption_unit: str
    purchase_cost: float = Field(ge=0)
    min_stock: float = Field(default=0, ge=0)
    tracks_lot: bool = False
    tracks_expiry: bool = False


class SupplyUpdateIn(BaseModel):
    """Solo las claves enviadas. Cambiar el costo no cambia el de lo ya registrado."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    brand: Optional[str] = Field(default=None, max_length=100, description="Vacío o null = sin marca")
    description: Optional[str] = Field(default=None, max_length=2000, description="Vacío o null = sin descripción")
    suppliers: Optional[list[SupplierIn]] = Field(default=None, description="Reemplaza la lista completa")
    category: Optional[str] = None
    purchase_unit: Optional[str] = Field(default=None, min_length=1, max_length=50)
    purchase_content: Optional[float] = Field(default=None, gt=0)
    consumption_unit: Optional[str] = None
    purchase_cost: Optional[float] = Field(default=None, ge=0)
    min_stock: Optional[float] = Field(default=None, ge=0)
    tracks_lot: Optional[bool] = None
    tracks_expiry: Optional[bool] = None
    is_active: Optional[bool] = None


# ─── Movimientos ─────────────────────────────────────────────────────────────

class MovementOut(BaseModel):
    id: UUID
    code: str                       # MOV-0001
    occurred_on: date
    type: str
    type_label: str
    supply_id: UUID
    sku: str
    supply_name: str
    consumption_unit: str
    quantity: float                 # + entra, − sale
    unit_cost: float                # costo por unidad al registrarlo
    cost: float                     # cantidad × costo por unidad (negativo si sale)
    location: Optional[str] = None
    cost_center: Optional[str] = None
    order_id: Optional[UUID] = None
    recipe_id: Optional[UUID] = None
    reason: str
    lot: Optional[str] = None
    expires_on: Optional[date] = None
    created_by: Optional[UUID] = None
    created_by_name: Optional[str] = Field(default=None, description="null = sistema (consumo automático)")
    created_at: datetime
    purchase_quantity: Optional[float] = Field(default=None, description="Cantidad en unidades de compra, si se ingresó así")
    purchase_price: Optional[float] = Field(default=None, description="S/ por unidad de compra pagado en esta entrada")
    voided_at: Optional[datetime] = Field(default=None, description="null = vigente; anulado no cuenta en el stock")
    voided_by: Optional[UUID] = None
    voided_by_name: Optional[str] = None
    void_reason: Optional[str] = None
    can_void: bool = Field(default=False, description="Manual y vigente: se puede anular")


class MovementVoidIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500, description="Motivo de la anulación")


class MovementCreateIn(BaseModel):
    type: Literal["initial_stock", "purchase", "consumption", "adjustment", "waste"]
    supply_id: UUID
    quantity: Optional[float] = Field(
        default=None, gt=0, description="En unidad de consumo, siempre positiva; el signo sale del tipo (o de direction). "
        "Enviar quantity o purchase_quantity, no ambos")
    purchase_quantity: Optional[float] = Field(
        default=None, gt=0, description="En unidades de compra (solo purchase / initial_stock); se convierte con el contenido")
    purchase_price: Optional[float] = Field(
        default=None, ge=0, description="S/ por unidad de compra. Obligatorio en purchase, opcional en initial_stock; "
        "el costo del insumo pasa al promedio ponderado")
    direction: Optional[Literal["in", "out"]] = Field(default=None, description="Obligatorio en adjustment")
    occurred_on: Optional[date] = Field(default=None, description="Por defecto hoy (Lima); no puede ser futura")
    location: Optional[str] = None
    cost_center: Optional[str] = None
    order_id: Optional[UUID] = None
    reason: str = Field(min_length=1, description="Motivo o comprobante (p. ej. Factura F001-1234)")
    lot: Optional[str] = Field(default=None, max_length=60)
    expires_on: Optional[date] = None


class InventorySummaryOut(BaseModel):
    inventory_value: float          # al día de hoy
    supplies_below_min: int         # bajo mínimo o agotados (activos)
    consumption_cost: float         # consumos por servicio del período
    orders_with_consumption: int
    avg_cost_per_order: Optional[float]


# ─── Recetas ─────────────────────────────────────────────────────────────────

class RecipeLineIn(BaseModel):
    supply_id: UUID
    quantity: float = Field(gt=0)


class RecipeCellIn(BaseModel):
    breed_category: str = Field(description="Tipo de pelaje o 'mestizo' (GET /admin/store/price-config)")
    weight_min: float = Field(ge=0)
    weight_max: Optional[float] = Field(default=None, ge=0, description="null = sin tope")
    labor_minutes: float = Field(default=0, ge=0, description="Minutos de groomer estimados")
    lines: list[RecipeLineIn] = Field(default_factory=list)


class RecipeSaveIn(BaseModel):
    target_type: Literal["product", "addon"]
    cells: list[RecipeCellIn] = Field(description="Tabla completa; las celdas sin insumos ni minutos se omiten")


class RecipeLineOut(BaseModel):
    supply_id: UUID
    sku: str
    supply_name: str
    consumption_unit: str
    quantity: float
    unit_cost: float
    cost: float


class RecipeCellOut(BaseModel):
    id: Optional[UUID] = None
    breed_category: str
    weight_min: float
    weight_max: Optional[float] = None
    labor_minutes: float
    lines: list[RecipeLineOut]
    supplies_cost: float = Field(description="Insumos con los costos actuales")
    labor_cost: Optional[float] = Field(default=None, description="Minutos × tarifa de referencia (null sin tarifa)")
    total_cost: float
    price: Optional[float] = Field(default=None, description="Precio (con IGV) de la misma celda en la tabla de precios")
    price_without_igv: Optional[float] = Field(default=None, description="Precio ÷ (1 + IGV)")
    margin: Optional[float] = Field(default=None, description="Precio sin IGV − costo total")


class RecipeOut(BaseModel):
    id: UUID
    target_type: Literal["product", "addon"]
    target_id: UUID
    target_name: Optional[str] = None
    version: int
    version_label: str              # R1, R2…
    is_current: bool
    cells: list[RecipeCellOut]
    labor_rate: Optional[float] = Field(default=None, description="S/ por hora de servicio usada en labor_cost")
    igv_percent: float = Field(description="IGV (%) de Parámetros generales con que se quitó el IGV al precio")
    created_at: datetime


class RecipeSummaryOut(BaseModel):
    target_type: str
    target_id: UUID
    target_name: Optional[str] = None
    version_label: str
    cells: int
    created_at: datetime


# ─── Costo por orden ─────────────────────────────────────────────────────────

class OrderCostLineOut(RecipeLineOut):
    recipe_id: Optional[UUID] = None
    recipe_version: Optional[str] = None


class OrderCostCellOut(BaseModel):
    target_type: str
    ref_id: str
    name: str
    recipe_id: UUID
    recipe_version: str
    breed_category: str = Field(description="Fila usada: el pelaje o 'mestizo' (respaldo)")
    weight_min: float
    weight_max: Optional[float] = None
    labor_minutes: float


class MissingRecipeOut(BaseModel):
    target_type: str
    ref_id: str
    name: str


class OrderCostOut(BaseModel):
    order_id: UUID
    status: str
    sale_total: float
    breed_category: str
    weight_kg: Optional[float] = None
    registered: bool = Field(description="True: insumos registrados; False: estimado con las recetas vigentes")
    lines: list[OrderCostLineOut]
    cells: list[OrderCostCellOut] = Field(description="Celdas de las recetas vigentes que aplican a la orden")
    missing_recipes: list[MissingRecipeOut]
    supplies_cost: float
    labor_rate: Optional[float] = Field(default=None, description="S/ por hora de servicio")
    labor_rate_source: str = Field(description="groomer (el de la orden) | reference (promedio)")
    estimated_minutes: float
    labor_cost_estimated: Optional[float] = None
    real_travel_minutes: Optional[float] = Field(default=None, description="Salida → llegada")
    real_service_minutes: Optional[float] = Field(default=None, description="Llegada → fin")
    labor_cost_real: Optional[float] = None
    total_cost_estimated: Optional[float] = Field(default=None, description="Insumos + mano de obra estimada")
    margin_estimated: Optional[float] = None
    margin_estimated_pct: Optional[float] = None
    total_cost_real: Optional[float] = Field(default=None, description="Insumos + mano de obra con el tiempo real")
    margin_real: Optional[float] = None


# ─── Capturas (feature 0015) ─────────────────────────────────────────────────

class SnapshotScheduleOut(BaseModel):
    frequency: str = Field(description="weekly | semimonthly | monthly | none (Parámetros generales)")
    frequency_label: str
    next_cut: Optional[date] = Field(default=None, description="Próximo corte; se captura al terminar ese día")


class SnapshotOut(BaseModel):
    id: UUID
    cut_date: date
    kind: str = Field(description="scheduled | manual")
    kind_label: str
    frequency: Optional[str] = None
    taken_at: datetime
    created_by: Optional[UUID] = Field(default=None, description="null = sistema")
    supplies_count: int
    total_value: float
    low_count: int
    out_count: int


class SnapshotListOut(BaseModel):
    schedule: SnapshotScheduleOut
    items: list[SnapshotOut]


class SnapshotLineOut(BaseModel):
    supply_id: UUID
    sku: str
    name: str
    category: str
    consumption_unit: str
    purchase_unit: str
    is_active: bool
    stock: float
    min_stock: float
    unit_cost: float
    value: float
    status: str = Field(description="ok | low | out")


class SnapshotDetailOut(SnapshotOut):
    lines: list[SnapshotLineOut]


# ─── Simulador de un servicio (feature 0019) ─────────────────────────────────

class SimulationIn(BaseModel):
    product_id: UUID
    addon_ids: list[UUID] = Field(default_factory=list)
    breed_id: Optional[str] = Field(None, description="Sin raza: fila «mestizo».")
    weight_kg: float
    groomer_id: Optional[UUID] = Field(None, description="Costo por hora de ese groomer; sin valor, el de referencia.")


class SimulationLineOut(BaseModel):
    supply_id: UUID
    sku: str
    supply_name: str
    consumption_unit: str
    quantity: float
    unit_cost: float
    cost: float


class SimulationItemOut(BaseModel):
    target_type: str
    target_id: UUID
    name: str
    price: Optional[float] = Field(None, description="null: sin precio para este pelaje y peso.")
    recipe_version: Optional[str] = Field(None, description="null: sin receta o sin celda para este pelaje y peso.")
    category_used: Optional[str] = None
    weight_min: Optional[float] = None
    weight_max: Optional[float] = None
    labor_minutes: float
    supplies_cost: float
    lines: list[SimulationLineOut]


class SimulationSupplyOut(BaseModel):
    supply_id: UUID
    sku: str
    supply_name: str
    consumption_unit: str
    quantity: float
    unit_cost: float
    cost: float
    cost_share_pct: Optional[float] = Field(None, description="% del costo de insumos del servicio.")
    stock: float
    min_stock: float
    stock_status: str
    services_with_stock: Optional[int] = Field(None, description="Servicios iguales que alcanzan con el stock de hoy.")


class SimulationOut(BaseModel):
    product_id: UUID
    product_name: str
    breed_id: Optional[str] = None
    breed_name: Optional[str] = None
    breed_category: str
    breed_category_label: str
    weight_kg: float
    weight_code: Optional[str] = None
    items: list[SimulationItemOut]
    supplies: list[SimulationSupplyOut]
    price: Optional[float] = Field(None, description="null si algún ítem no tiene precio.")
    supplies_cost: float
    labor_minutes: float
    labor_rate: Optional[float] = None
    labor_rate_source: str
    labor_cost: Optional[float] = None
    total_cost: Optional[float] = None
    margin: Optional[float] = None
    margin_pct: Optional[float] = None
    max_services_with_stock: Optional[int] = Field(None, description="El insumo que primero se acaba manda.")
    warnings: list[str]
