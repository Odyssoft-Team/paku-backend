"""Parámetros generales (feature 0010)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.modules.general_settings.domain.settings import (
    FIELDS_BY_KEY,
    SettingInvalid,
    check_consistency,
    resolve,
    validate_value,
)


def _invalid(exc: SettingInvalid) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": "SETTING_INVALID", "message": exc.message, "key": exc.key})


@dataclass
class GetSettings:
    repo: Any

    async def execute(self) -> dict[str, Any]:
        """Valor efectivo de cada parámetro (lo guardado o el valor por defecto)."""
        return resolve(await self.repo.get_all())


@dataclass
class UpdateSettings:
    repo: Any

    async def execute(self, values: dict[str, Any], *, actor_id: UUID) -> dict[str, Any]:
        """Cambia solo las claves enviadas; `null` vuelve al valor por defecto. Todo o nada."""
        if not values:
            raise HTTPException(status_code=422, detail={"code": "SETTING_INVALID", "message": "No hay cambios."})
        try:
            clean = {key: validate_value(key, value) for key, value in values.items()}
            stored = await self.repo.get_all()
            check_consistency(resolve({**stored, **clean}))
        except SettingInvalid as exc:
            raise _invalid(exc) from exc
        await self.repo.save(clean, updated_by=actor_id)
        return resolve({**stored, **clean})


async def get_setting(repo: Any, key: str) -> Any:
    """Valor efectivo de un parámetro, para usarlo desde otros módulos."""
    field = FIELDS_BY_KEY[key]
    if not field.editable:
        return field.default
    value = await repo.get(key)
    return field.default if value is None else value


async def booking_min_days_ahead(session) -> int:
    """Días mínimos de anticipación para reservar (0 = hoy). Lo usa booking."""
    from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository

    return int(await get_setting(PostgresSettingsRepository(session=session), "booking_min_days_ahead") or 0)
