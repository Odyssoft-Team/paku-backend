from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, create_access_token, decode_token
from app.core.db import engine, get_async_session
from app.modules.iam.api.schemas import AddressOut, LoginIn, RefreshIn, RegisterIn, TokenOut, UpdateProfileIn, UserOut
from app.modules.iam.app.use_cases import GetMe, LoginUser, RegisterUser, UpdateProfile
from app.modules.iam.domain.user import Address, Sex
from app.modules.iam.domain.user import UserRepository
from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository

# [TECH]
# This FastAPI router exposes the IAM (Identity & Access Management) HTTP handlers.
# It is the entry point for:
# - authentication (register/login/refresh)
# - basic identity operations (get/update current profile)
# It orchestrates DTO validation (pydantic schemas), delegates business rules to use cases,
# and uses the auth utilities to mint/validate JWTs. It depends on:
# - app.core.auth for token creation/decoding and current_user extraction
# - app.modules.iam.app.use_cases for IAM business logic
# - app.modules.iam.infra.user_repository for persistence (in-memory in this project)
#
# [BUSINESS]
# Esta sección define las rutas del sistema de identidad.
# Permite que un usuario se registre, inicie sesión y renueve su sesión.
# También permite consultar y actualizar los datos del perfil del usuario autenticado.
router = APIRouter(tags=["iam"])
security = HTTPBearer()


def get_user_repo(session: AsyncSession = Depends(get_async_session)) -> UserRepository:
    return PostgresUserRepository(session=session, engine=engine)


async def get_current_user_db(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    repo: UserRepository = Depends(get_user_repo),
) -> CurrentUser:
    token = credentials.credentials
    data = decode_token(token)
    if data.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        from uuid import UUID

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
# This handler registers a new user.
# Inputs: RegisterIn (email, password, personal data, optional address).
# Output: UserOut representation of the created user.
# Flow: authentication (account creation). Delegates to RegisterUser use case and
# maps the domain Address object back to an API AddressOut.
# Depends on: RegisterUser (business rules) + InMemoryUserRepository (storage).
#
# [BUSINESS]
# Esta ruta crea una cuenta nueva en el sistema.
# Recibe los datos del usuario (incluyendo contraseña) y devuelve el perfil ya creado.
# Es el primer paso para que alguien pueda empezar a usar la plataforma.
async def register(payload: RegisterIn, repo: UserRepository = Depends(get_user_repo)) -> UserOut:
    address_domain = None
    if payload.address:
        address_domain = Address(
            district_id=payload.address.district_id,
            address_line=payload.address.address_line,
            lat=payload.address.lat,
            lng=payload.address.lng,
        )
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
        address=address_domain,
        profile_photo_url=payload.profile_photo_url,
    )
    result = user.__dict__.copy()
    if user.address:
        result["address"] = AddressOut(
            district_id=user.address.district_id,
            address_line=user.address.address_line,
            lat=user.address.lat,
            lng=user.address.lng,
        )
    return UserOut(**result)


@router.post("/auth/login", response_model=TokenOut)
# [TECH]
# This handler authenticates a user using email/password.
# Inputs: LoginIn (email, password).
# Output: TokenOut with access_token + refresh_token.
# Flow: authentication (login). Delegates credential validation to LoginUser.
# Depends on: LoginUser (hash comparison, active user check) + token utilities.
#
# [BUSINESS]
# Esta ruta permite iniciar sesión.
# Si el usuario y contraseña son correctos, devuelve los tokens necesarios para
# mantener la sesión activa en la app.
async def login(payload: LoginIn, repo: UserRepository = Depends(get_user_repo)) -> TokenOut:
    tokens = await LoginUser(repo=repo).execute(email=payload.email, password=payload.password)
    return TokenOut(**tokens)


@router.post("/auth/refresh", response_model=TokenOut)
# [TECH]
# This handler issues a new access token using a refresh token.
# Inputs: RefreshIn (refresh_token).
# Output: TokenOut with a newly minted access_token and the same refresh_token.
# Flow: authentication (token renewal). It decodes the refresh token, validates its type,
# and mints a new access token with the embedded user claims.
# Depends on: decode_token + create_access_token.
#
# [BUSINESS]
# Esta ruta renueva la sesión del usuario sin pedirle que vuelva a ingresar su contraseña.
# Si el refresh token es válido, se entrega un nuevo access token para seguir usando la app.
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
# This handler returns the current authenticated user's profile.
# Inputs: current (CurrentUser) extracted from the Bearer access token.
# Output: UserOut.
# Flow: identity/profile. Delegates lookup to GetMe.
# Depends on: get_current_user (auth dependency) + GetMe use case.
#
# [BUSINESS]
# Esta ruta devuelve "mi perfil": los datos del usuario que está autenticado.
# Se usa para mostrar la información del usuario en la app (nombre, correo, etc.).
async def me(current: CurrentUser = Depends(get_current_user_db), repo: UserRepository = Depends(get_user_repo)) -> UserOut:
    user = await GetMe(repo=repo).execute(user_id=current.id)
    result = user.__dict__.copy()
    if user.address:
        result["address"] = AddressOut(
            district_id=user.address.district_id,
            address_line=user.address.address_line,
            lat=user.address.lat,
            lng=user.address.lng,
        )
    return UserOut(**result)


@router.put("/users/me", response_model=UserOut)
# [TECH]
# This handler updates the current authenticated user's profile.
# Inputs: UpdateProfileIn (optional fields to change) + current (CurrentUser from token).
# Output: UserOut of the updated user.
# Flow: identity/profile update. Delegates update logic to UpdateProfile.
# Depends on: get_current_user + UpdateProfile use case.
#
# [BUSINESS]
# Esta ruta permite que el usuario actualice su información personal (por ejemplo teléfono,
# nombre, dirección o foto). Solo modifica el perfil del usuario que está logueado.
async def update_me(
    payload: UpdateProfileIn,
    current: CurrentUser = Depends(get_current_user_db),
    repo: UserRepository = Depends(get_user_repo),
) -> UserOut:
    address_domain = None
    if payload.address:
        address_domain = Address(
            district_id=payload.address.district_id,
            address_line=payload.address.address_line,
            lat=payload.address.lat,
            lng=payload.address.lng,
        )
    user = await UpdateProfile(repo=repo).execute(
        user_id=current.id,
        phone=payload.phone,
        first_name=payload.first_name,
        last_name=payload.last_name,
        sex=Sex(payload.sex) if payload.sex else None,
        birth_date=payload.birth_date,
        dni=payload.dni,
        address=address_domain,
        profile_photo_url=payload.profile_photo_url,
    )
    result = user.__dict__.copy()
    if user.address:
        result["address"] = AddressOut(
            district_id=user.address.district_id,
            address_line=user.address.address_line,
            lat=user.address.lat,
            lng=user.address.lng,
        )
    return UserOut(**result)
