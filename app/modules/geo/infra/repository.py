"""Geo infrastructure repository.

Postgres implementation of the DistrictRepository protocol.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.domain import DistrictRepository
from app.modules.geo.infra.model import DistrictModel


class PostgresDistrictRepository:
    """Postgres implementation for district catalog queries."""
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def list_districts(self, active_only: bool = True) -> list[dict]:
        """List all districts, optionally filtering by active status."""
        stmt = select(DistrictModel)
        if active_only:
            stmt = stmt.where(DistrictModel.active)
        
        stmt = stmt.order_by(DistrictModel.name)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        
        return [
            {
                "id": model.id,
                "name": model.name,
                "province_name": model.province_name,
                "department_name": model.department_name,
                "active": model.active,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
            }
            for model in models
        ]
    
    async def get_district(self, id: str) -> Optional[dict]:
        """Get a single district by its ID. Returns None if not found."""
        model = await self._session.get(DistrictModel, id)
        if model is None:
            return None
        
        return {
            "id": model.id,
            "name": model.name,
            "province_name": model.province_name,
            "department_name": model.department_name,
            "active": model.active,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
