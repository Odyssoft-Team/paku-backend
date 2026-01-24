from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.iam.domain.user import Address, Sex, User, UserRepository
from app.modules.iam.infra.models import UserModel, ensure_iam_schema, utcnow


def _to_domain(model: UserModel) -> User:
    address = None
    if (
        model.address_district_id is not None
        and model.address_line is not None
        and model.address_lat is not None
        and model.address_lng is not None
    ):
        address = Address(
            district_id=model.address_district_id,
            address_line=model.address_line,
            lat=float(model.address_lat),
            lng=float(model.address_lng),
        )

    return User(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        role=model.role,  # type: ignore[arg-type]
        is_active=bool(model.is_active),
        created_at=model.created_at,
        phone=model.phone,
        first_name=model.first_name,
        last_name=model.last_name,
        sex=Sex(model.sex),
        birth_date=model.birth_date,
        dni=model.dni,
        address=address,
        profile_photo_url=model.profile_photo_url,
    )


class PostgresUserRepository(UserRepository):
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def get_by_email(self, email: str) -> Optional[User]:
        await ensure_iam_schema(self._engine)

        stmt = select(UserModel).where(UserModel.email == email.strip().lower())
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        if model is None:
            return None
        return _to_domain(model)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        await ensure_iam_schema(self._engine)

        model = await self._session.get(UserModel, user_id)
        if model is None:
            return None
        return _to_domain(model)

    async def add(self, user: User) -> None:
        await ensure_iam_schema(self._engine)

        address_district_id: Optional[str] = None
        address_line: Optional[str] = None
        address_lat: Optional[float] = None
        address_lng: Optional[float] = None
        if user.address is not None:
            address_district_id = user.address.district_id
            address_line = user.address.address_line
            address_lat = float(user.address.lat)
            address_lng = float(user.address.lng)

        model = UserModel(
            id=user.id,
            email=user.email.strip().lower(),
            password_hash=user.password_hash,
            role=str(user.role),
            is_active=bool(user.is_active),
            phone=user.phone,
            first_name=user.first_name,
            last_name=user.last_name,
            sex=str(user.sex.value if hasattr(user.sex, "value") else user.sex),
            birth_date=user.birth_date,
            dni=user.dni,
            address_district_id=address_district_id,
            address_line=address_line,
            address_lat=address_lat,
            address_lng=address_lng,
            profile_photo_url=user.profile_photo_url,
            created_at=user.created_at,
            updated_at=utcnow(),
        )
        self._session.add(model)
        await self._session.commit()

    async def update(self, user: User) -> None:
        await ensure_iam_schema(self._engine)

        model = await self._session.get(UserModel, user.id)
        if model is None:
            raise ValueError("user_not_found")

        model.phone = user.phone
        model.first_name = user.first_name
        model.last_name = user.last_name
        model.sex = str(user.sex.value if hasattr(user.sex, "value") else user.sex)
        model.birth_date = user.birth_date
        model.dni = user.dni
        model.profile_photo_url = user.profile_photo_url

        if user.address is None:
            model.address_district_id = None
            model.address_line = None
            model.address_lat = None
            model.address_lng = None
        else:
            model.address_district_id = user.address.district_id
            model.address_line = user.address.address_line
            model.address_lat = float(user.address.lat)
            model.address_lng = float(user.address.lng)

        model.updated_at = utcnow()

        await self._session.commit()
