"""Geo infrastructure repository.

HARDCODED implementation using in-memory data.

NOTE: For MVP/early development we use hardcoded districts from
`districts_data.py`.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo.infra.districts_data import get_all_districts, get_district_by_id


class PostgresDistrictRepository:
    """District repository using hardcoded data.

    NOTE: Despite the name 'Postgres', this implementation does not hit the DB.
    The session parameter is kept only for compatibility with the dependency
    injection wiring and for potential future reintroduction of a DB catalog.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session  # Not used

    async def list_districts(self, active_only: bool = True) -> list[dict]:
        districts = get_all_districts(active_only=active_only)
        return sorted(districts, key=lambda d: d["name"])

    async def get_district(self, id: str) -> Optional[dict]:
        return get_district_by_id(id)
