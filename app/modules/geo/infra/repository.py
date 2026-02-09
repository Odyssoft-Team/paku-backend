"""Geo infrastructure repository.

HARDCODED implementation using in-memory data.
This allows the platform to work without populating geo_districts table.

NOTE: For MVP, we use hardcoded districts from districts_data.py.
In the future, this can be switched back to database queries or external API.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.domain import DistrictRepository
from app.modules.geo.infra.districts_data import get_all_districts, get_district_by_id


class PostgresDistrictRepository:
    """District repository using hardcoded data.
    
    NOTE: Despite the name 'Postgres', this now uses hardcoded data
    to avoid dependency on populated geo_districts table.
    The session parameter is kept for future compatibility.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session  # Kept for future use, not used now
    
    async def list_districts(self, active_only: bool = True) -> list[dict]:
        """List all districts from hardcoded data.
        
        Args:
            active_only: If True, return only active districts.
        
        Returns:
            List of district dictionaries.
        """
        # Use hardcoded data instead of DB query
        districts = get_all_districts(active_only=active_only)
        # Sort by name for consistent ordering
        return sorted(districts, key=lambda d: d["name"])
    
    async def get_district(self, id: str) -> Optional[dict]:
        """Get a single district by its ID from hardcoded data.
        
        Args:
            id: The district UBIGEO code.
        
        Returns:
            District dictionary or None if not found.
        """
        # Use hardcoded data instead of DB query
        return get_district_by_id(id)
