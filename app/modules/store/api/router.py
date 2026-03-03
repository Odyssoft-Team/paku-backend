from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import engine, get_async_session
from app.modules.store.api.schemas import (
    AddonCreateIn,
    AddonOut,
    AddonUpdateIn,
    CategoryCreateIn,
    CategoryOut,
    CategoryUpdateIn,
    PriceRuleCreateIn,
    PriceRuleOut,
    PriceRuleUpdateIn,
    ProductCreateIn,
    ProductDetailOut,
    ProductOut,
    ProductUpdateIn,
    QuoteIn,
    QuoteOut,
    ToggleIn,
)
from app.modules.store.app.use_cases import (
    CreateAddon,
    CreateCategory,
    CreatePriceRule,
    CreateProduct,
    GetProduct,
    ListAllAddons,
    ListAllCategories,
    ListAllProducts,
    ListCategories,
    ListPriceRules,
    ListProducts,
    Quote,
    ToggleAddon,
    ToggleCategory,
    ToggleProduct,
    UpdateAddon,
    UpdateCategory,
    UpdatePriceRule,
    UpdateProduct,
)
from app.modules.store.domain.models import Species
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
from app.modules.pets.domain.pet import PetRepository


router = APIRouter(tags=["store"], prefix="/store")
admin_router = APIRouter(tags=["store-admin"])


def get_store_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresStoreRepository:
    return PostgresStoreRepository(session=session, engine=engine)


def get_pets_repo(session: AsyncSession = Depends(get_async_session)) -> PetRepository:
    return PostgresPetRepository(session=session, engine=engine)


# ------------------------------------------------------------------
# Endpoints públicos
# ------------------------------------------------------------------

@router.get("/categories", response_model=List[CategoryOut])
async def list_categories(
    species: Optional[Species] = Query(None),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> List[CategoryOut]:
    items = await ListCategories(repo=repo).execute(species=species)
    return [CategoryOut(**c.__dict__) for c in items]


@router.get("/categories/{slug}/products", response_model=List[ProductOut])
async def list_products(
    slug: str,
    pet_id: Optional[UUID] = Query(None),
    species: Optional[Species] = Query(None),
    repo: PostgresStoreRepository = Depends(get_store_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
) -> List[ProductOut]:
    items = await ListProducts(repo=repo, pets_repo=pets_repo).execute(
        category_slug=slug, pet_id=pet_id, species=species
    )
    return [ProductOut(**rp.product.__dict__, price=rp.price) for rp in items]


@router.get("/products/{id}", response_model=ProductDetailOut)
async def get_product(
    id: UUID,
    pet_id: Optional[UUID] = Query(None),
    repo: PostgresStoreRepository = Depends(get_store_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
) -> ProductDetailOut:
    rp, addons = await GetProduct(repo=repo, pets_repo=pets_repo).execute(product_id=id, pet_id=pet_id)
    return ProductDetailOut(
        **rp.product.__dict__,
        price=rp.price,
        available_addons=[AddonOut(**ra.addon.__dict__, price=ra.price) for ra in addons],
    )


@router.post("/quote", response_model=QuoteOut)
async def quote(
    payload: QuoteIn,
    _: CurrentUser = Depends(get_current_user),
    repo: PostgresStoreRepository = Depends(get_store_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
) -> QuoteOut:
    result = await Quote(repo=repo, pets_repo=pets_repo).execute(
        pet_id=payload.pet_id,
        product_id=payload.product_id,
        addon_ids=payload.addon_ids,
    )
    return QuoteOut(
        pet_id=result.pet_id,
        product=result.product.__dict__,
        addons=[a.__dict__ for a in result.addons],
        total=result.total,
        currency=result.currency,
    )


# ------------------------------------------------------------------
# Admin — categorías
# ------------------------------------------------------------------

@admin_router.get("/store/categories", response_model=List[CategoryOut])
async def admin_list_categories(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> List[CategoryOut]:
    items = await ListAllCategories(repo=repo).execute()
    return [CategoryOut(**c.__dict__) for c in items]


@admin_router.post("/store/categories", response_model=CategoryOut, status_code=201)
async def admin_create_category(
    payload: CategoryCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> CategoryOut:
    category = await CreateCategory(repo=repo).execute(
        name=payload.name, slug=payload.slug, species=payload.species, is_active=payload.is_active
    )
    return CategoryOut(**category.__dict__)


@admin_router.patch("/store/categories/{id}", response_model=CategoryOut)
async def admin_update_category(
    id: UUID,
    payload: CategoryUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> CategoryOut:
    category = await UpdateCategory(repo=repo).execute(id, name=payload.name, species=payload.species)
    return CategoryOut(**category.__dict__)


@admin_router.post("/store/categories/{id}/toggle", response_model=CategoryOut)
async def admin_toggle_category(
    id: UUID,
    payload: ToggleIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> CategoryOut:
    category = await ToggleCategory(repo=repo).execute(id, is_active=payload.is_active)
    return CategoryOut(**category.__dict__)


# ------------------------------------------------------------------
# Admin — productos
# ------------------------------------------------------------------

@admin_router.get("/store/products", response_model=List[ProductOut])
async def admin_list_products(
    category_id: UUID = Query(...),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> List[ProductOut]:
    items = await ListAllProducts(repo=repo).execute(category_id=category_id)
    return [ProductOut(**p.__dict__) for p in items]


@admin_router.post("/store/products", response_model=ProductOut, status_code=201)
async def admin_create_product(
    payload: ProductCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> ProductOut:
    product = await CreateProduct(repo=repo).execute(
        category_id=payload.category_id,
        name=payload.name,
        description=payload.description,
        species=payload.species,
        allowed_breeds=payload.allowed_breeds,
        is_active=payload.is_active,
    )
    return ProductOut(**product.__dict__)


@admin_router.patch("/store/products/{id}", response_model=ProductOut)
async def admin_update_product(
    id: UUID,
    payload: ProductUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> ProductOut:
    product = await UpdateProduct(repo=repo).execute(
        id, name=payload.name, description=payload.description, allowed_breeds=payload.allowed_breeds
    )
    return ProductOut(**product.__dict__)


@admin_router.post("/store/products/{id}/toggle", response_model=ProductOut)
async def admin_toggle_product(
    id: UUID,
    payload: ToggleIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> ProductOut:
    product = await ToggleProduct(repo=repo).execute(id, is_active=payload.is_active)
    return ProductOut(**product.__dict__)


# ------------------------------------------------------------------
# Admin — addons
# ------------------------------------------------------------------

@admin_router.get("/store/addons", response_model=List[AddonOut])
async def admin_list_addons(
    product_id: UUID = Query(...),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> List[AddonOut]:
    items = await ListAllAddons(repo=repo).execute(product_id=product_id)
    return [AddonOut(**a.__dict__) for a in items]


@admin_router.post("/store/addons", response_model=AddonOut, status_code=201)
async def admin_create_addon(
    payload: AddonCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> AddonOut:
    addon = await CreateAddon(repo=repo).execute(
        product_id=payload.product_id,
        name=payload.name,
        description=payload.description,
        species=payload.species,
        allowed_breeds=payload.allowed_breeds,
        is_active=payload.is_active,
    )
    return AddonOut(**addon.__dict__)


@admin_router.patch("/store/addons/{id}", response_model=AddonOut)
async def admin_update_addon(
    id: UUID,
    payload: AddonUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> AddonOut:
    addon = await UpdateAddon(repo=repo).execute(
        id, name=payload.name, description=payload.description, allowed_breeds=payload.allowed_breeds
    )
    return AddonOut(**addon.__dict__)


@admin_router.post("/store/addons/{id}/toggle", response_model=AddonOut)
async def admin_toggle_addon(
    id: UUID,
    payload: ToggleIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> AddonOut:
    addon = await ToggleAddon(repo=repo).execute(id, is_active=payload.is_active)
    return AddonOut(**addon.__dict__)


# ------------------------------------------------------------------
# Admin — price rules
# ------------------------------------------------------------------

@admin_router.get("/store/price-rules", response_model=List[PriceRuleOut])
async def admin_list_price_rules(
    target_id: UUID = Query(...),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> List[PriceRuleOut]:
    rules = await ListPriceRules(repo=repo).execute(target_id=target_id)
    return [PriceRuleOut(**r.__dict__) for r in rules]


@admin_router.post("/store/price-rules", response_model=PriceRuleOut, status_code=201)
async def admin_create_price_rule(
    payload: PriceRuleCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> PriceRuleOut:
    rule = await CreatePriceRule(repo=repo).execute(
        target_id=payload.target_id,
        target_type=payload.target_type,
        species=payload.species,
        breed_category=payload.breed_category,
        weight_min=payload.weight_min,
        weight_max=payload.weight_max,
        price=payload.price,
        currency=payload.currency,
    )
    return PriceRuleOut(**rule.__dict__)


@admin_router.patch("/store/price-rules/{id}", response_model=PriceRuleOut)
async def admin_update_price_rule(
    id: UUID,
    payload: PriceRuleUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresStoreRepository = Depends(get_store_repo),
) -> PriceRuleOut:
    rule = await UpdatePriceRule(repo=repo).execute(
        id,
        price=payload.price,
        weight_min=payload.weight_min,
        weight_max=payload.weight_max,
        is_active=payload.is_active,
    )
    return PriceRuleOut(**rule.__dict__)
