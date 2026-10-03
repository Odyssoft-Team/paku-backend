from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.auth import CurrentUser
from app.modules.pets.domain.pet import PetRepository


async def check_pet_access(
    pet_id: Optional[UUID], current: Optional[CurrentUser], pets_repo: PetRepository,
) -> None:
    """Cotizar para una mascota revela especie, raza y peso: solo su dueño (o un admin).
    Sin pet_id el catálogo sigue siendo público."""
    if pet_id is None:
        return
    if current is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to use pet_id")
    if current.role == "admin":
        return
    pet = await pets_repo.get_by_id(pet_id)
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
    if pet.owner_id != current.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
