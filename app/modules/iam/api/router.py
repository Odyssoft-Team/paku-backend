from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.auth import CurrentUser, create_access_token, decode_token
from app.core.db import engine, get_async_session
from app.modules.iam.api.schemas import (
    AddressCreateIn,
    AddressOutExtended,
    AddressUpdateIn,
    DistrictOut,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UpdateProfileIn,
    UserOut,
)
from app.modules.iam.app.use_cases import GetMe, LoginUser, RegisterUser, UpdateProfile
from app.modules.iam.domain.user import Sex
from app.modules.iam.domain.user import UserRepository
from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository

# [TECH]
# This FastAPI router exposes the IAM (Identity & Access Management) HTTP handlers.
# It is the entry point for:
# - authentication (register/login/refresh)
# - basic identity operations (get/update current profile)
# - geo lookups (districts)
# - address book management (/addresses)
#
# It orchestrates DTO validation (pydantic schemas), delegates business rules to use cases,
# and uses the auth utilities to mint/validate JWTs.
#
# Key dependencies:
# - app.core.auth for token creation/decoding and current_user extraction
# - app.modules.iam.app.use_cases for IAM business logic
# - app.modules.iam.infra.postgres_user_repository for persistence and geo/address operations
#
# NOTE: In this implementation PostgresUserRepository.get_district/list_districts return dicts.
#
# [BUSINESS]
# Esta sección define las rutas del sistema de identidad.
# Permite que un usuario se registre, inicie sesión y renueve su sesión.
# También permite consultar y actualizar los datos del perfil del usuario autenticado.
# Además incluye:
# - consultas geográficas de distritos
# - gestión de libreta de direcciones del usuario (/addresses)
router = APIRouter(tags=["iam"])
security = HTTPBearer()


def get_user_repo(session: AsyncSession = Depends(get_async_session)) -> UserRepository:
    # [TECH] Repository factory (per-request session injected by FastAPI)
    # [BUSINESS] Acceso a datos de usuarios, distritos y direcciones.
    return PostgresUserRepository(session=session, engine=engine)


async def get_current_user_db(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    repo: UserRepository = Depends(get_user_repo),
) -> CurrentUser:
    # [TECH]
    # Extracts Bearer token, decodes JWT, validates it's an access token,
    # loads user from DB, verifies is_active, returns CurrentUser claims.
    #
    # [BUSINESS]
    # Obtiene el usuario autenticado a partir del token enviado por la app.
    token = credentials.credentials
    data = decode_token(token)
    if data.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = UUID(str(data.get("sub")))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    return CurrentUser(id=user.id, email=user.email, role=str(user.role), is_active=user.is_active)


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
# [TECH]
# Registers a new user without address support.
# Address book is managed exclusively via /addresses endpoints.
#
# [BUSINESS]
# Crea una cuenta nueva en el sistema y devuelve el perfil creado.
async def register(payload: RegisterIn, repo: UserRepository = Depends(get_user_repo)) -> UserOut:
    user = await RegisterUser(repo=repo).execute(
        email=payload.email,
        password=payload.password,
        phone=payload.phone,
        first_name=payload.first_name,
        last_name=payload.last_name,
        sex=Sex(payload.sex),
        birth_date=payload.birth_date,
        role=payload.role,
        dni=payload.dni,
        address=None,
        profile_photo_url=payload.profile_photo_url,
    )

    result = user.__dict__.copy()
    return UserOut(**result)


@router.post("/auth/login", response_model=TokenOut)
# [TECH]
# Authenticates user credentials and returns access/refresh tokens.
#
# [BUSINESS]
# Permite iniciar sesión y obtener tokens de sesión.
async def login(payload: LoginIn, repo: UserRepository = Depends(get_user_repo)) -> TokenOut:
    tokens = await LoginUser(repo=repo).execute(email=payload.email, password=payload.password)
    return TokenOut(**tokens)


@router.post("/auth/refresh", response_model=TokenOut)
# [TECH]
# Renews access token using a refresh token.
#
# [BUSINESS]
# Renueva la sesión del usuario sin pedir contraseña.
async def refresh(payload: RefreshIn) -> TokenOut:
    data = decode_token(payload.refresh_token)
    if data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    access_token = create_access_token(
        user_id=data.get("sub"),
        email=data.get("email"),
        role=data.get("role"),
    )
    return TokenOut(access_token=access_token, refresh_token=payload.refresh_token)


@router.get("/users/me", response_model=UserOut)
# [TECH]
# Returns current user profile without address (address book lives in /addresses).
#
# [BUSINESS]
# Devuelve "mi perfil" del usuario autenticado (sin dirección de perfil).
async def me(
    current: CurrentUser = Depends(get_current_user_db),
    repo: UserRepository = Depends(get_user_repo),
) -> UserOut:
    user = await GetMe(repo=repo).execute(user_id=current.id)
    result = user.__dict__.copy()
    # Address book is now exclusively in /addresses
    return UserOut(**result)


@router.put("/users/me", response_model=UserOut)
# [TECH]
# Updates current user profile.
# IMPORTANT: profile.address is deprecated; users must use /addresses endpoints.
#
# [BUSINESS]
# Actualiza datos del perfil (teléfono, nombre, etc.). Dirección del perfil ya no se edita aquí.
async def update_me(
    payload: UpdateProfileIn,
    current: CurrentUser = Depends(get_current_user_db),
    repo: UserRepository = Depends(get_user_repo),
) -> UserOut:
    if payload.address is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Profile address is deprecated. Use /addresses endpoints.",
        )

    user = await UpdateProfile(repo=repo).execute(
        user_id=current.id,
        phone=payload.phone,
        first_name=payload.first_name,
        last_name=payload.last_name,
        sex=Sex(payload.sex) if payload.sex else None,
        birth_date=payload.birth_date,
        dni=payload.dni,
        address=None,
        profile_photo_url=payload.profile_photo_url,
    )

    result = user.__dict__.copy()
    # Address book is now exclusively in /addresses
    return UserOut(**result)


@router.get("/geo/districts", response_model=list[DistrictOut])
# [TECH]
# Lists districts. Repo returns list[dict]; we map dict -> DistrictOut.
#
# [BUSINESS]
# Lista distritos (por defecto solo activos) para selección en UI.
async def list_geo_districts(
    active: bool = Query(default=True),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> list[DistrictOut]:
    items = await repo.list_districts(active_only=active)
    return [
        DistrictOut(
            id=i["id"],
            name=i["name"],
            province_name=i.get("province_name"),
            department_name=i.get("department_name"),
            active=i["active"],
        )
        for i in items
    ]


@router.get("/geo/districts/{district_id}", response_model=DistrictOut)
# [TECH]
# Gets a district by id. Repo returns dict or None; we map to DistrictOut.
#
# [BUSINESS]
# Devuelve un distrito específico.
async def get_geo_district(
    district_id: str,
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> DistrictOut:
    item = await repo.get_district(district_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")

    return DistrictOut(
        id=item["id"],
        name=item["name"],
        province_name=item.get("province_name"),
        department_name=item.get("department_name"),
        active=item["active"],
    )


# [TECH]
# User address management endpoints.
# These endpoints require authentication and provide CRUD operations for user addresses.
# They use the existing PostgresUserRepository methods for address management.
#
# Notes:
# - We validate District existence + active on create/update (when district_id is provided).
# - We DO NOT auto-use "default" for orders. Orders must receive address_id explicitly.
# - Default is only a UX helper (suggested address in UI) and should not change constantly.
#
# [BUSINESS]
# Gestión de libreta de direcciones del usuario.
# Permite crear, listar, actualizar, eliminar y marcar dirección por defecto.
# En el flujo de compra, el usuario elige una dirección y la orden recibe address_id explícito.

@router.get("/addresses", response_model=list[AddressOutExtended])
async def list_addresses(
    current: CurrentUser = Depends(get_current_user_db),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> list[AddressOutExtended]:
    """List all addresses for the current user."""
    addresses = await repo.list_addresses_by_user(user_id=current.id)
    return [
        AddressOutExtended(
            id=addr["id"],
            district_id=addr["district_id"],
            address_line=addr["address_line"],
            lat=addr["lat"],
            lng=addr["lng"],
            reference=addr.get("reference"),
            building_number=addr.get("building_number"),
            apartment_number=addr.get("apartment_number"),
            label=addr.get("label"),
            type=addr.get("type"),
            is_default=addr["is_default"],
            created_at=addr["created_at"],
        )
        for addr in addresses
    ]


@router.post("/addresses", response_model=AddressOutExtended, status_code=status.HTTP_201_CREATED)
async def create_address(
    payload: AddressCreateIn,
    current: CurrentUser = Depends(get_current_user_db),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> AddressOutExtended:
    """Create a new address for the current user."""
    # Validate district exists and is active
    district = await repo.get_district(payload.district_id)
    if not district:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")
    if district["active"] is not True:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="District is not active")

    # Determine if this is the first address BEFORE creating it
    existing_before = await repo.list_addresses_by_user(user_id=current.id)

    # Create address
    address = await repo.create_address(user_id=current.id, address_data=payload.model_dump())

    # Default is a UX helper. We only auto-default the very first address,
    # or when the client explicitly requests is_default=true.
    if len(existing_before) == 0 or bool(payload.is_default):
        await repo.set_default_address(user_id=current.id, address_id=address["id"])
        refreshed = await repo.get_address_for_user(user_id=current.id, address_id=address["id"])
        if refreshed:
            address = refreshed

    return AddressOutExtended(
        id=address["id"],
        district_id=address["district_id"],
        address_line=address["address_line"],
        lat=address["lat"],
        lng=address["lng"],
        reference=address.get("reference"),
        building_number=address.get("building_number"),
        apartment_number=address.get("apartment_number"),
        label=address.get("label"),
        type=address.get("type"),
        is_default=address["is_default"],
        created_at=address["created_at"],
    )


@router.get("/addresses/{address_id}", response_model=AddressOutExtended)
async def get_address(
    address_id: UUID,
    current: CurrentUser = Depends(get_current_user_db),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> AddressOutExtended:
    """Get a specific address by ID."""
    address = await repo.get_address_for_user(user_id=current.id, address_id=address_id)
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")

    return AddressOutExtended(
        id=address["id"],
        district_id=address["district_id"],
        address_line=address["address_line"],
        lat=address["lat"],
        lng=address["lng"],
        reference=address.get("reference"),
        building_number=address.get("building_number"),
        apartment_number=address.get("apartment_number"),
        label=address.get("label"),
        type=address.get("type"),
        is_default=address["is_default"],
        created_at=address["created_at"],
    )


@router.put("/addresses/{address_id}", response_model=AddressOutExtended)
async def update_address(
    address_id: UUID,
    payload: AddressUpdateIn,
    current: CurrentUser = Depends(get_current_user_db),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> AddressOutExtended:
    """Update a specific address."""
    # Validate district if provided
    if payload.district_id:
        district = await repo.get_district(payload.district_id)
        if not district:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")
        if district["active"] is not True:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="District is not active")

    # Update address (ownership and deleted_at are validated inside repository)
    try:
        address = await repo.update_address(
            user_id=current.id,
            address_id=address_id,
            patch=payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        if str(exc) == "address_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found") from exc
        raise

    return AddressOutExtended(
        id=address["id"],
        district_id=address["district_id"],
        address_line=address["address_line"],
        lat=address["lat"],
        lng=address["lng"],
        reference=address.get("reference"),
        building_number=address.get("building_number"),
        apartment_number=address.get("apartment_number"),
        label=address.get("label"),
        type=address.get("type"),
        is_default=address["is_default"],
        created_at=address["created_at"],
    )


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: UUID,
    current: CurrentUser = Depends(get_current_user_db),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> None:
    """Soft delete a specific address."""
    try:
        await repo.soft_delete_address(user_id=current.id, address_id=address_id)
    except ValueError as exc:
        if str(exc) == "address_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found") from exc
        if str(exc) == "no_addresses_left":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete last address") from exc
        raise


@router.put("/addresses/{address_id}/default", status_code=status.HTTP_204_NO_CONTENT)
async def set_default_address(
    address_id: UUID,
    current: CurrentUser = Depends(get_current_user_db),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> None:
    """Set an address as the default address."""
    try:
        await repo.set_default_address(user_id=current.id, address_id=address_id)
    except ValueError as exc:
        if str(exc) == "address_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found") from exc
        raise
