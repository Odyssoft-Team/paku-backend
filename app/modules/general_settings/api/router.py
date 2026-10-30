"""Parámetros generales de la empresa (feature 0010). Solo admin."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.modules.general_settings.api.schemas import (
    GeneralSettingsOut,
    GeneralSettingsUpdateIn,
    SettingFieldOut,
    SettingSectionOut,
)
from app.modules.general_settings.app.use_cases import GetSettings, UpdateSettings
from app.modules.general_settings.domain.settings import FIELDS, SECTIONS
from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository

admin_router = APIRouter(tags=["settings-admin"])


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresSettingsRepository:
    return PostgresSettingsRepository(session=session)


async def _settings_out(values: dict[str, Any], repo: PostgresSettingsRepository) -> GeneralSettingsOut:
    updated_at, updated_by = await repo.last_update()
    sections = [
        SettingSectionOut(code=code, title=title, fields=[
            SettingFieldOut(key=f.key, label=f.label, type=f.type, value=values.get(f.key), default=f.default,
                            editable=f.editable, help=f.help, min=f.min, max=f.max)
            for f in FIELDS if f.section == code
        ])
        for code, title in SECTIONS.items()
    ]
    return GeneralSettingsOut(values=values, sections=sections, updated_at=updated_at, updated_by=updated_by)


@admin_router.get("/settings", response_model=GeneralSettingsOut)
async def get_settings(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresSettingsRepository = Depends(get_repo),
) -> GeneralSettingsOut:
    """Datos de la empresa y valores por defecto de la plataforma, por sección."""
    return await _settings_out(await GetSettings(repo=repo).execute(), repo)


@admin_router.patch("/settings", response_model=GeneralSettingsOut)
async def update_settings(
    payload: GeneralSettingsUpdateIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresSettingsRepository = Depends(get_repo),
) -> GeneralSettingsOut:
    """
    Cambia solo las claves enviadas (`null` vuelve al valor por defecto). Todo o nada: si una no es válida
    responde 422 `SETTING_INVALID` con `key` y no guarda ninguna. Los de solo lectura no se cambian.
    """
    values = await UpdateSettings(repo=repo).execute(payload.values, actor_id=current.id)
    return await _settings_out(values, repo)
