"""Geo domain protocols (interfaces).

Defines the contract that any geo repository must implement.
"""

from typing import Optional, Protocol


class DistrictRepository(Protocol):
    """Protocol for district catalog access."""
    
    async def list_districts(self, active_only: bool = True) -> list[dict]:
        """List all districts, optionally filtering by active status."""
        ...
    
    async def get_district(self, id: str) -> Optional[dict]:
        """Get a single district by its ID. Returns None if not found."""
        ...
