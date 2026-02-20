from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.paku_spa.api.schemas import PakuSpaPlanOut
from app.modules.paku_spa.domain.plans_data import PLANS
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository


router = APIRouter(prefix="/paku-spa", tags=["paku-spa"])


def get_pets_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresPetRepository:
    return PostgresPetRepository(session=session, engine=engine)


@router.get("/plans", response_model=List[PakuSpaPlanOut])
async def list_plans(
    pet_id: Optional[UUID] = Query(None, description="UUID de la mascota (opcional, para validar flujo)"),
    current: CurrentUser = Depends(get_current_user),
    pets_repo: PostgresPetRepository = Depends(get_pets_repo),
) -> List[PakuSpaPlanOut]:
    """
    Lista los planes hardcoded de Paku Spa.
    
    Si se proporciona pet_id:
    - Valida que la mascota existe y pertenece al usuario
    - Estructura el flujo correcto (mascota → servicio → dirección → fecha → pago)
    
    El precio actual es fijo hardcoded. En el futuro se calculará según peso de la mascota.
    """
    # Si viene pet_id, validar que existe y pertenece al usuario
    if pet_id is not None:
        pet = await pets_repo.get_by_id(pet_id)
        if pet is None or pet.owner_id != current.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pet not found or does not belong to user"
            )
    
    # Devolver planes hardcoded (precio fijo por ahora)
    return [PakuSpaPlanOut(**p) for p in PLANS]
