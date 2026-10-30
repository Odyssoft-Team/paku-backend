from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.general_settings.infra.models import GeneralSettingModel, utcnow


class PostgresSettingsRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> dict[str, Any]:
        rows = (await self._session.execute(select(GeneralSettingModel))).scalars().all()
        return {r.key: r.value for r in rows}

    async def last_update(self) -> tuple[Optional[datetime], Optional[UUID]]:
        stmt = select(GeneralSettingModel.updated_at, GeneralSettingModel.updated_by).order_by(
            GeneralSettingModel.updated_at.desc()
        ).limit(1)
        row = (await self._session.execute(stmt)).first()
        return (row.updated_at, row.updated_by) if row else (None, None)

    async def get(self, key: str) -> Any:
        stmt = select(GeneralSettingModel.value).where(GeneralSettingModel.key == key)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def save(self, values: dict[str, Any], *, updated_by: UUID) -> None:
        """Guarda o reemplaza cada clave; `None` borra la fila (vuelve al valor por defecto)."""
        now = utcnow()
        for key, value in values.items():
            model = await self._session.get(GeneralSettingModel, key)
            if value is None:
                if model is not None:
                    await self._session.delete(model)
                continue
            if model is None:
                self._session.add(GeneralSettingModel(key=key, value=value, updated_by=updated_by, updated_at=now))
            else:
                model.value = value
                model.updated_by = updated_by
                model.updated_at = now
        await self._session.commit()
