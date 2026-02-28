from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import engine, get_async_session
from app.modules.commerce.api.schemas import (
    PriceRuleCreateIn,
    PriceRuleOut,
    PriceRuleUpdateIn,
    QuoteIn,
    QuoteOut,
    ServiceAvailableOut,
    ServiceCreateIn,
    ServiceOut,
    ServiceToggleIn,
    ServiceUpdateIn,
)
from app.modules.commerce.app.use_cases import (
    CreatePriceRule,
    CreateService,
    ListAllServices,
    ListAvailableServices,
    ListPriceRules,
    ListServices,
    Quote,
    ToggleService,
    UpdatePriceRule,
    UpdateService,
)
from app.modules.commerce.domain.service import Species
from app.modules.commerce.infra.postgres_commerce_repository import PostgresCommerceRepository
from app.modules.pets.domain.pet import PetRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository

# [TECH] Router HTTP de Commerce: expone catálogo, disponibles por mascota y cotización (precios/addons).
# [NEGOCIO] Permite a la app ver servicios ofrecidos y calcular cuánto se cobrará.
router = APIRouter(tags=["commerce"])


def get_commerce_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresCommerceRepository:
    return PostgresCommerceRepository(session=session, engine=engine)


def get_pets_repo(session: AsyncSession = Depends(get_async_session)) -> PetRepository:
    return PostgresPetRepository(session=session, engine=engine)


@router.get("/services", response_model=List[ServiceOut])
# [TECH] Lista servicios del catálogo filtrando por especie/raza. Output: List[ServiceOut]. Flujo: catálogo/reglas.
# [NEGOCIO] Muestra al cliente los servicios que aplican a su mascota.
async def get_services(
    species: Species = Query(...),
    breed: Optional[str] = Query(None),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
) -> List[ServiceOut]:
    services = await ListServices(repo=repo).execute(species=species, breed=breed)
    return [ServiceOut(**s.__dict__) for s in services]


@router.get("/services/available", response_model=List[ServiceAvailableOut])
# [TECH] Devuelve bases y addons aplicables para un pet_id. Requiere token. Flujo: catálogo/addons/reglas.
# [NEGOCIO] Indica qué opciones puede contratar el cliente para esa mascota.
async def get_available_services(
    pet_id: UUID = Query(...),
    _: CurrentUser = Depends(get_current_user),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
) -> List[ServiceAvailableOut]:
    items = await ListAvailableServices(repo=repo, pets_repo=pets_repo).execute(pet_id=pet_id)
    out: List[ServiceAvailableOut] = []
    for item in items:
        out.append(
            ServiceAvailableOut(
                **item.base.__dict__,
                available_addons=[ServiceOut(**a.__dict__) for a in item.available_addons],
            )
        )
    return out


@router.post("/quote", response_model=QuoteOut)
# [TECH] Calcula cotización (base + addons) según especie/raza/peso. Input: QuoteIn. Flujo: precios/reglas/addons.
# [NEGOCIO] Determina el total a cobrar por el servicio y sus adicionales.
async def create_quote(
    payload: QuoteIn,
    _: CurrentUser = Depends(get_current_user),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
) -> QuoteOut:
    result = await Quote(repo=repo, pets_repo=pets_repo).execute(
        pet_id=payload.pet_id,
        base_service_id=payload.base_service_id,
        addon_ids=payload.addon_ids,
    )
    return QuoteOut(
        pet_id=result.pet_id,
        base=result.base.__dict__,
        addons=[a.__dict__ for a in result.addons],
        total=result.total,
        currency=result.currency,
    )


# ------------------------------------------------------------------
# Admin — services
# ------------------------------------------------------------------

@router.get("/admin/services", response_model=List[ServiceOut])
async def admin_list_services(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
) -> List[ServiceOut]:
    services = await ListAllServices(repo=repo).execute()
    return [ServiceOut(**s.__dict__) for s in services]


@router.post("/admin/services", response_model=ServiceOut, status_code=201)
async def admin_create_service(
    payload: ServiceCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
) -> ServiceOut:
    service = await CreateService(repo=repo).execute(
        name=payload.name,
        type=payload.type,
        species=payload.species,
        allowed_breeds=payload.allowed_breeds,
        requires=payload.requires,
        is_active=payload.is_active,
    )
    return ServiceOut(**service.__dict__)


@router.patch("/admin/services/{service_id}", response_model=ServiceOut)
async def admin_update_service(
    service_id: UUID,
    payload: ServiceUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
) -> ServiceOut:
    service = await UpdateService(repo=repo).execute(
        service_id,
        name=payload.name,
        allowed_breeds=payload.allowed_breeds,
        requires=payload.requires,
    )
    return ServiceOut(**service.__dict__)


@router.post("/admin/services/{service_id}/toggle", response_model=ServiceOut)
async def admin_toggle_service(
    service_id: UUID,
    payload: ServiceToggleIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
) -> ServiceOut:
    service = await ToggleService(repo=repo).execute(service_id, is_active=payload.is_active)
    return ServiceOut(**service.__dict__)


# ------------------------------------------------------------------
# Admin — price rules
# ------------------------------------------------------------------

@router.get("/admin/services/{service_id}/price-rules", response_model=List[PriceRuleOut])
async def admin_list_price_rules(
    service_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
) -> List[PriceRuleOut]:
    rules = await ListPriceRules(repo=repo).execute(service_id)
    return [PriceRuleOut(**r.__dict__) for r in rules]


@router.post("/admin/price-rules", response_model=PriceRuleOut, status_code=201)
async def admin_create_price_rule(
    payload: PriceRuleCreateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
) -> PriceRuleOut:
    rule = await CreatePriceRule(repo=repo).execute(
        service_id=payload.service_id,
        species=payload.species,
        breed_category=payload.breed_category,
        weight_min=payload.weight_min,
        weight_max=payload.weight_max,
        price=payload.price,
        currency=payload.currency,
    )
    return PriceRuleOut(**rule.__dict__)


@router.patch("/admin/price-rules/{rule_id}", response_model=PriceRuleOut)
async def admin_update_price_rule(
    rule_id: UUID,
    payload: PriceRuleUpdateIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCommerceRepository = Depends(get_commerce_repo),
) -> PriceRuleOut:
    rule = await UpdatePriceRule(repo=repo).execute(
        rule_id,
        price=payload.price,
        weight_min=payload.weight_min,
        weight_max=payload.weight_max,
        is_active=payload.is_active,
    )
    return PriceRuleOut(**rule.__dict__)
