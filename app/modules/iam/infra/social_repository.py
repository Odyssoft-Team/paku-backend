from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.iam.domain.social_identity import SocialIdentity, SocialIdentityRepository
from app.modules.iam.infra.models import UserSocialIdentityModel


def _to_domain(model: UserSocialIdentityModel) -> SocialIdentity:
    return SocialIdentity(
        id=model.id,
        user_id=model.user_id,
        provider=model.provider,
        firebase_uid=model.firebase_uid,
        created_at=model.created_at,
    )


class PostgresSocialIdentityRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def get_by_firebase_uid(self, firebase_uid: str) -> Optional[SocialIdentity]:
        stmt = select(UserSocialIdentityModel).where(
            UserSocialIdentityModel.firebase_uid == firebase_uid
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _to_domain(model)

    async def add(self, identity: SocialIdentity) -> None:
        model = UserSocialIdentityModel(
            id=identity.id,
            user_id=identity.user_id,
            provider=identity.provider,
            firebase_uid=identity.firebase_uid,
            created_at=identity.created_at,
        )
        self._session.add(model)
        await self._session.commit()
