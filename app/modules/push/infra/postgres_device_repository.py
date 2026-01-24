from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.push.domain.push import DeviceToken, DeviceTokenRepository, Platform


class PostgresDeviceTokenRepository(DeviceTokenRepository):
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def register_device(self, user_id: UUID, platform: Platform, token: str) -> DeviceToken:
        from app.modules.push.infra.models import DeviceTokenModel

        # Upsert lógico: buscar existente por (user_id, platform) y actualizar token si existe
        stmt = select(DeviceTokenModel).where(
            DeviceTokenModel.user_id == user_id, DeviceTokenModel.platform == platform
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update token y reactivar
            stmt_update = (
                update(DeviceTokenModel)
                .where(DeviceTokenModel.id == existing.id)
                .values(token=token, is_active=True)
                .returning(DeviceTokenModel)
            )
            result_update = await self._session.execute(stmt_update)
            row = result_update.scalar_one()
        else:
            # Insertar nuevo
            device = DeviceToken.new(user_id=user_id, platform=platform, token=token)
            row = DeviceTokenModel(
                id=device.id,
                user_id=device.user_id,
                platform=device.platform,
                token=device.token,
                is_active=device.is_active,
                created_at=device.created_at,
            )
            self._session.add(row)
            await self._session.flush()

        return DeviceToken(
            id=row.id,
            user_id=row.user_id,
            platform=row.platform,
            token=row.token,
            is_active=row.is_active,
            created_at=row.created_at,
        )

    async def list_devices(self, user_id: UUID) -> list[DeviceToken]:
        from app.modules.push.infra.models import DeviceTokenModel

        stmt = select(DeviceTokenModel).where(DeviceTokenModel.user_id == user_id).order_by(
            DeviceTokenModel.created_at.desc()
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            DeviceToken(
                id=row.id,
                user_id=row.user_id,
                platform=row.platform,
                token=row.token,
                is_active=row.is_active,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def deactivate_device(self, device_id: UUID, user_id: UUID) -> DeviceToken:
        from app.modules.push.infra.models import DeviceTokenModel

        stmt = (
            update(DeviceTokenModel)
            .where(DeviceTokenModel.id == device_id, DeviceTokenModel.user_id == user_id)
            .values(is_active=False)
            .returning(DeviceTokenModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            raise ValueError("device_not_found")

        return DeviceToken(
            id=row.id,
            user_id=row.user_id,
            platform=row.platform,
            token=row.token,
            is_active=row.is_active,
            created_at=row.created_at,
        )

    async def get_active_tokens(self, user_id: UUID) -> list[str]:
        from app.modules.push.infra.models import DeviceTokenModel

        stmt = select(DeviceTokenModel.token).where(
            DeviceTokenModel.user_id == user_id, DeviceTokenModel.is_active.is_(True)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
