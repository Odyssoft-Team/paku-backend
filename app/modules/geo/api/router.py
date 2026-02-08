"""Geo API router.

Public endpoints for the geo catalog (districts).
Maintains backward compatibility with existing /geo/districts paths.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.modules.geo.domain.schemas import DistrictOut
from app.modules.geo.infra.repository import PostgresDistrictRepository
from app.modules.geo.use_cases.geo_service import GeoService

router = APIRouter(tags=["geo"])


def get_geo_service(session: AsyncSession = Depends(get_async_session)) -> GeoService:
    """Factory for GeoService with injected repository."""
    repo = PostgresDistrictRepository(session=session)
    return GeoService(district_repo=repo)


@router.get("/districts", response_model=list[DistrictOut])
async def list_districts(
    active: bool = Query(default=True),
    service: GeoService = Depends(get_geo_service),
) -> list[DistrictOut]:
    """List all districts.
    
    By default returns only active districts for UI selection.
    """
    return await service.list_districts(active_only=active)


@router.get("/districts/{district_id}", response_model=DistrictOut)
async def get_district(
    district_id: str,
    service: GeoService = Depends(get_geo_service),
) -> DistrictOut:
    """Get a specific district by ID."""
    district = await service.get_district(district_id)
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District not found"
        )
    return district
