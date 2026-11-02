from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.infra.models import ChannelProviderModel


class PostgresChannelRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def get(self, channel: str) -> Optional[ChannelProviderModel]:
        return await self._session.get(ChannelProviderModel, channel)

    async def save(self, model: ChannelProviderModel) -> ChannelProviderModel:
        self._session.add(model)
        await self._session.commit()
        return model
