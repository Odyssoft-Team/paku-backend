"""Geo service use cases.

Business logic for the geo catalog (read-only for districts).
"""

from typing import Optional

from app.modules.geo.domain import DistrictRepository
from app.modules.geo.domain.schemas import DistrictOut


class GeoService:
    """Service for geo catalog operations."""
    
    def __init__(self, district_repo: DistrictRepository) -> None:
        self._district_repo = district_repo
    
    async def list_districts(self, active_only: bool = True) -> list[DistrictOut]:
        """List all districts."""
        items = await self._district_repo.list_districts(active_only=active_only)
        return [
            DistrictOut(
                id=item["id"],
                name=item["name"],
                province_name=item.get("province_name"),
                department_name=item.get("department_name"),
                active=item["active"],
            )
            for item in items
        ]
    
    async def get_district(self, district_id: str) -> Optional[DistrictOut]:
        """Get a single district by ID."""
        item = await self._district_repo.get_district(district_id)
        if item is None:
            return None
        
        return DistrictOut(
            id=item["id"],
            name=item["name"],
            province_name=item.get("province_name"),
            department_name=item.get("department_name"),
            active=item["active"],
        )
    
    async def validate_district_exists_and_active(self, district_id: str) -> bool:
        """Validate that a district exists and is active.
        
        Used by other modules (e.g., IAM addresses) to validate district references.
        """
        district = await self._district_repo.get_district(district_id)
        if district is None:
            return False
        return district.get("active", False) is True
