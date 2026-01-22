from typing import List, Optional

from fastapi import APIRouter, Query

from app.modules.commerce.api.schemas import ServiceOut
from app.modules.commerce.app.use_cases import ListServices
from app.modules.commerce.domain.service import Species

router = APIRouter(tags=["commerce"])


@router.get("/services", response_model=List[ServiceOut])
async def get_services(
    species: Species = Query(...),
    breed: Optional[str] = Query(None),
) -> List[ServiceOut]:
    services = ListServices().execute(species=species, breed=breed)
    return [ServiceOut(**s.__dict__) for s in services]
