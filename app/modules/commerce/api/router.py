from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.modules.commerce.api.schemas import QuoteOut, QuoteIn, ServiceAvailableOut, ServiceOut
from app.modules.commerce.app.use_cases import Quote, ListAvailableServices, ListServices
from app.modules.commerce.domain.service import Species

router = APIRouter(tags=["commerce"])


@router.get("/services", response_model=List[ServiceOut])
async def get_services(
    species: Species = Query(...),
    breed: Optional[str] = Query(None),
) -> List[ServiceOut]:
    services = ListServices().execute(species=species, breed=breed)
    return [ServiceOut(**s.__dict__) for s in services]


@router.get("/services/available", response_model=List[ServiceAvailableOut])
async def get_available_services(
    pet_id: UUID = Query(...),
    _: CurrentUser = Depends(get_current_user),
) -> List[ServiceAvailableOut]:
    items = await ListAvailableServices().execute(pet_id=pet_id)
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
async def create_quote(payload: QuoteIn, _: CurrentUser = Depends(get_current_user)) -> QuoteOut:
    result = await Quote().execute(
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
