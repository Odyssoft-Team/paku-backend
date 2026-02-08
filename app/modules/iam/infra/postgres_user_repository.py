from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.iam.domain.user import Address, Sex, User, UserRepository, AddressRepository
from app.modules.iam.infra.models import UserModel, UserAddressModel, utcnow


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


class PostgresUserRepository(UserRepository, AddressRepository):
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def get_by_email(self, email: str) -> Optional[User]:

        stmt = select(UserModel).where(UserModel.email == email.strip().lower())
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        if model is None:
            return None
        return _to_domain(model)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:

        model = await self._session.get(UserModel, user_id)
        if model is None:
            return None
        return _to_domain(model)

    async def add(self, user: User) -> None:

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

    # AddressRepository methods
    async def list_addresses_by_user(self, user_id: UUID, include_deleted: bool = False) -> list[dict]:

        stmt = select(UserAddressModel).where(UserAddressModel.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(UserAddressModel.deleted_at.is_(None))
        
        stmt = stmt.order_by(UserAddressModel.is_default.desc(), UserAddressModel.created_at.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [
            {
                "id": model.id,
                "user_id": model.user_id,
                "district_id": model.district_id,
                "address_line": model.address_line,
                "reference": model.reference,
                "building_number": model.building_number,
                "apartment_number": model.apartment_number,
                "label": model.label,
                "type": model.type,
                "lat": model.lat,
                "lng": model.lng,
                "is_default": model.is_default,
                "deleted_at": model.deleted_at,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
            }
            for model in models
        ]

    async def get_address_for_user(self, user_id: UUID, address_id: UUID) -> Optional[dict]:

        stmt = select(UserAddressModel).where(
            UserAddressModel.user_id == user_id,
            UserAddressModel.id == address_id,
            UserAddressModel.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None

        return {
            "id": model.id,
            "user_id": model.user_id,
            "district_id": model.district_id,
            "address_line": model.address_line,
            "reference": model.reference,
            "building_number": model.building_number,
            "apartment_number": model.apartment_number,
            "label": model.label,
            "type": model.type,
            "lat": model.lat,
            "lng": model.lng,
            "is_default": model.is_default,
            "deleted_at": model.deleted_at,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    async def create_address(self, user_id: UUID, address_data: dict) -> dict:

        model = UserAddressModel(
            user_id=user_id,
            district_id=address_data["district_id"],
            address_line=address_data["address_line"],
            reference=address_data.get("reference"),
            building_number=address_data.get("building_number"),
            apartment_number=address_data.get("apartment_number"),
            label=address_data.get("label"),
            type=address_data.get("type"),
            lat=address_data["lat"],
            lng=address_data["lng"],
            is_default=address_data.get("is_default", False),
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        return {
            "id": model.id,
            "user_id": model.user_id,
            "district_id": model.district_id,
            "address_line": model.address_line,
            "reference": model.reference,
            "building_number": model.building_number,
            "apartment_number": model.apartment_number,
            "label": model.label,
            "type": model.type,
            "lat": model.lat,
            "lng": model.lng,
            "is_default": model.is_default,
            "deleted_at": model.deleted_at,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    async def update_address(self, user_id: UUID, address_id: UUID, patch: dict) -> dict:

        stmt = select(UserAddressModel).where(
            UserAddressModel.user_id == user_id,
            UserAddressModel.id == address_id,
            UserAddressModel.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            raise ValueError("address_not_found")

        # Update fields
        for key, value in patch.items():
            if key == "is_default":
                continue  # is_default se maneja solo por set_default_address
            if hasattr(model, key) and key not in ["id", "user_id", "created_at", "deleted_at"]:
                setattr(model, key, value)
        
        model.updated_at = utcnow()
        await self._session.commit()
        await self._session.refresh(model)

        return {
            "id": model.id,
            "user_id": model.user_id,
            "district_id": model.district_id,
            "address_line": model.address_line,
            "reference": model.reference,
            "building_number": model.building_number,
            "apartment_number": model.apartment_number,
            "label": model.label,
            "type": model.type,
            "lat": model.lat,
            "lng": model.lng,
            "is_default": model.is_default,
            "deleted_at": model.deleted_at,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    async def soft_delete_address(self, user_id: UUID, address_id: UUID) -> None:

        # Get address to delete
        stmt = select(UserAddressModel).where(
            UserAddressModel.user_id == user_id,
            UserAddressModel.id == address_id,
            UserAddressModel.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            raise ValueError("address_not_found")

        was_default = model.is_default
        
        # Soft delete
        model.deleted_at = utcnow()
        model.is_default = False
        model.updated_at = utcnow()

        # If it was default, assign new default
        if was_default:
            new_default_stmt = select(UserAddressModel).where(
                UserAddressModel.user_id == user_id,
                UserAddressModel.deleted_at.is_(None),
                UserAddressModel.id != address_id
            ).order_by(UserAddressModel.created_at.desc()).limit(1)
            
            new_default_result = await self._session.execute(new_default_stmt)
            new_default_model = new_default_result.scalar_one_or_none()
            
            if new_default_model:
                new_default_model.is_default = True
                new_default_model.updated_at = utcnow()
            else:
                raise ValueError("no_addresses_left")

        await self._session.commit()

    async def set_default_address(self, user_id: UUID, address_id: UUID) -> None:

        # Verify address exists and is not deleted
        stmt = select(UserAddressModel).where(
            UserAddressModel.user_id == user_id,
            UserAddressModel.id == address_id,
            UserAddressModel.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            raise ValueError("address_not_found")

        # Set all other addresses to non-default
        from sqlalchemy import update
        await self._session.execute(
            update(UserAddressModel)
            .where(
                UserAddressModel.user_id == user_id,
                UserAddressModel.deleted_at.is_(None),
                UserAddressModel.id != address_id
            )
            .values(is_default=False, updated_at=utcnow())
        )

        # Set this address as default
        model.is_default = True
        model.updated_at = utcnow()

        await self._session.commit()

    async def get_default_address(self, user_id: UUID) -> Optional[dict]:

        stmt = select(UserAddressModel).where(
            UserAddressModel.user_id == user_id,
            UserAddressModel.is_default,
            UserAddressModel.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None

        return {
            "id": model.id,
            "user_id": model.user_id,
            "district_id": model.district_id,
            "address_line": model.address_line,
            "reference": model.reference,
            "building_number": model.building_number,
            "apartment_number": model.apartment_number,
            "label": model.label,
            "type": model.type,
            "lat": model.lat,
            "lng": model.lng,
            "is_default": model.is_default,
            "deleted_at": model.deleted_at,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
