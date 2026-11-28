from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.auth import CurrentUser, create_access_token, decode_token, get_current_user, normalize_role, require_roles
from app.core.db import engine, get_async_session
from app.core.rate_limiter import forgot_password_limiter, login_limiter
from app.modules.geo.infra.repository import PostgresDistrictRepository
from app.modules.geo.use_cases.geo_service import GeoService
from app.modules.iam.api.schemas import (
    DniConsultaIn,
    DniConsultaOut,
    AddressCreateIn,
    AddressOutExtended,
    AddressUpdateIn,
    AdminCreateUserIn,
    ChangeRoleIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    SetPasswordIn,
    TokenOut,
    UpdateProfileIn,
    UserOut,
    UserSearchResultOut,
)
from app.modules.iam.app.use_cases import ChangeUserRole, GetMe, LoginUser, RegisterUser, UpdateProfile
from app.modules.iam.app.use_cases_impl.account_linking import AddPassword
from app.modules.iam.app.use_cases_impl.password_reset import ForgotPassword, ResetPassword
from app.modules.iam.app.use_cases_impl.consulta_dni import CacheDni, ConsultarDni, LimiteConsultaDni, LimitesConsultaDni
from app.modules.iam.domain.dni import (
    ConsultaDniLimitada,
    ConsultaDniNoDisponible,
    ConsultorDni,
    DatosDni,
    DniNoEncontrado,
)
from app.modules.iam.domain.user import campos_faltantes
from app.modules.hcvet.api.router import obtener_repositorio_hcvet
from app.modules.hcvet.app.servicio import ServicioIntegracionHcvet, campos_cambiados_para_hcvet
from app.modules.iam.infra.consultor_dni import obtener_consultor_dni
from app.core.settings import settings
from app.media.gcs import to_signed_read_url_or_none
from app.modules.iam.domain.user import Sex, User
from app.modules.iam.domain.user import UserRepository
from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository

# [TECH]
# This FastAPI router exposes the IAM (Identity & Access Management) HTTP handlers.
# It is the entry point for:
# - authentication (register/login/refresh)
# - basic identity operations (get/update current profile)
# - address book management (/addresses)
#
# It orchestrates DTO validation (pydantic schemas), delegates business rules to use cases,
# and uses the auth utilities to mint/validate JWTs.
#
# Key dependencies:
# - app.core.auth for token creation/decoding and current_user extraction
# - app.modules.iam.app.use_cases for IAM business logic
# - app.modules.iam.infra.postgres_user_repository for persistence and address operations
#
# [BUSINESS]
# Esta sección define las rutas del sistema de identidad.
# Permite que un usuario se registre, inicie sesión y renueve su sesión.
# También permite consultar y actualizar los datos del perfil del usuario autenticado.
# Además incluye gestión de libreta de direcciones del usuario (/addresses).
router = APIRouter(tags=["iam"])
admin_router = APIRouter(tags=["iam-admin"])
security = HTTPBearer()


def get_user_repo(session: AsyncSession = Depends(get_async_session)) -> UserRepository:
    # [TECH] Repository factory (per-request session injected by FastAPI)
    # [BUSINESS] Acceso a datos de usuarios y direcciones.
    return PostgresUserRepository(session=session, engine=engine)


def get_geo_service(session: AsyncSession = Depends(get_async_session)) -> GeoService:
    # [TECH] GeoService factory for district validation.
    # [BUSINESS] Validación de distritos para direcciones.
    repo = PostgresDistrictRepository(session=session)
    return GeoService(district_repo=repo)


def _user_to_out(user: User) -> UserOut:
    """Construye UserOut resolviendo profile_photo_url (object key en BD) a una signed read URL fresca."""
    data = user.__dict__.copy()
    data["profile_photo_url"] = to_signed_read_url_or_none(user.profile_photo_url)
    # Feature 0027: lo que le falta al perfil (p. ej. DNI de un cliente existente que debe regularizar).
    data["missing_profile_fields"] = campos_faltantes(user, exigir_dni=settings.DNI_OBLIGATORIO)
    # Nombres legales (oficiales del DNI), separados del nombre visible. No prueban titularidad.
    legales = data.pop("datos_legales", None)
    data["legal_first_name"] = legales.nombres if legales else None
    data["legal_last_name"] = legales.apellidos if legales else None
    data["legal_data_source"] = legales.fuente if legales else None
    data["legal_data_checked_at"] = legales.consultado_en if legales else None
    return UserOut(**data)


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
    user = await RegisterUser(repo=repo, buscar_datos_oficiales=buscar_datos_oficiales).execute(
        email=payload.email,
        password=payload.password,
        phone=payload.phone,
        first_name=payload.first_name,
        last_name=payload.last_name,
        sex=Sex(payload.sex),
        birth_date=payload.birth_date,
        role="user",  # siempre user en registro público
        dni=payload.dni,
        address=None,
        profile_photo_url=None,  # managed exclusively via POST /media/confirm-profile-photo
    )

    return _user_to_out(user)


@router.post("/auth/login", response_model=TokenOut)
# [TECH]
# Authenticates user credentials and returns access/refresh tokens.
# Rate limited: 5 failed attempts per IP per 15 minutes.
#
# [BUSINESS]
# Permite iniciar sesión y obtener tokens de sesión.
async def login(request: Request, payload: LoginIn, repo: UserRepository = Depends(get_user_repo)) -> TokenOut:
    ip = request.client.host if request.client else "unknown"
    login_limiter.check(ip)
    try:
        tokens = await LoginUser(repo=repo).execute(email=payload.email, password=payload.password)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            login_limiter.record_failure(ip)
        raise
    login_limiter.record_success(ip)
    return TokenOut(**tokens)


@router.put("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
# [TECH]
# Agrega o cambia la contraseña del usuario autenticado.
# - Cuentas sociales sin contraseña: solo new_password.
# - Cuentas con contraseña: requiere current_password para verificar.
#
# [BUSINESS]
# Permite al usuario establecer o cambiar su contraseña.
async def set_password(
    payload: SetPasswordIn,
    current: CurrentUser = Depends(get_current_user_db),
    repo: UserRepository = Depends(get_user_repo),
) -> None:
    await AddPassword(repo=repo).execute(
        user_id=current.id,
        new_password=payload.new_password,
        current_password=payload.current_password,
    )


class _ForgotPasswordIn:
    pass


from pydantic import BaseModel as _BaseModel, EmailStr as _EmailStr


class ForgotPasswordIn(_BaseModel):
    email: _EmailStr


class ResetPasswordIn(_BaseModel):
    token: str
    new_password: str


@router.post("/auth/forgot-password", status_code=status.HTTP_200_OK)
# [TECH]
# Genera un token de reset de contraseña para el email dado.
# Siempre responde 200 para no revelar si el email existe.
# Rate limited: 3 intentos por IP por hora.
#
# [BUSINESS]
# Inicia el flujo de recuperación de contraseña.
async def forgot_password(
    request: Request,
    payload: ForgotPasswordIn,
    repo: UserRepository = Depends(get_user_repo),
) -> dict:
    ip = request.client.host if request.client else "unknown"
    forgot_password_limiter.check(ip)
    forgot_password_limiter.record_failure(ip)  # cuenta el intento
    await ForgotPassword(repo=repo).execute(email=payload.email)
    return {"detail": "Si el email existe recibirás un enlace de recuperación"}


@router.post("/auth/reset-password", status_code=status.HTTP_204_NO_CONTENT)
# [TECH]
# Valida el token de reset y actualiza la contraseña.
#
# [BUSINESS]
# Completa el flujo de recuperación de contraseña con el token recibido.
async def reset_password(
    payload: ResetPasswordIn,
    repo: UserRepository = Depends(get_user_repo),
) -> None:
    await ResetPassword(repo=repo).execute(token=payload.token, new_password=payload.new_password)


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
        role=normalize_role(data.get("role")),
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
    # Address book is now exclusively in /addresses
    return _user_to_out(user)


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
    hcvet_repo=Depends(obtener_repositorio_hcvet),
) -> UserOut:
    # Feature 0028: con el propietario vinculado en HCVet el DNI no cambia aquí (identifica al propietario en HCVet).
    hcvet = ServicioIntegracionHcvet(hcvet_repo, activa=settings.HCVET_INTEGRACION_ACTIVA)
    antes = await repo.get_by_id(current.id)
    if payload.dni and antes is not None and payload.dni != antes.dni and await hcvet.dni_bloqueado(current.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DNI_LOCKED_BY_HCVET",
                "message": "Tu DNI está vinculado a tu historial en HCVet y no se puede cambiar desde aquí.",
            },
        )
    user = await UpdateProfile(repo=repo, buscar_datos_oficiales=buscar_datos_oficiales).execute(
        user_id=current.id,
        phone=payload.phone,
        first_name=payload.first_name,
        last_name=payload.last_name,
        sex=Sex(payload.sex) if payload.sex else None,
        birth_date=payload.birth_date,
        dni=payload.dni,
        address=None,
        profile_photo_url=None,  # managed exclusively via POST /media/confirm-profile-photo
    )
    # Feature 0028: avisar a HCVet los datos básicos que cambiaron (se encola; no llama a HCVet ni falla por él).
    if antes is not None:
        await hcvet.notificar_cambio_perfil(current.id, campos_cambiados_para_hcvet(antes, user))

    # Address book is now exclusively in /addresses
    return _user_to_out(user)


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
    geo: GeoService = Depends(get_geo_service),
) -> AddressOutExtended:
    """Create a new address for the current user."""
    # Validate district exists and is active via Geo service
    if not await geo.validate_district_exists_and_active(payload.district_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="District not found or not active")

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


@router.patch("/addresses/{address_id}", response_model=AddressOutExtended)
async def update_address(
    address_id: UUID,
    payload: AddressUpdateIn,
    current: CurrentUser = Depends(get_current_user_db),
    repo: PostgresUserRepository = Depends(get_user_repo),
    geo: GeoService = Depends(get_geo_service),
) -> AddressOutExtended:
    """Update a specific address (partial update)."""
    # Validate district if provided via Geo service
    if payload.district_id:
        if not await geo.validate_district_exists_and_active(payload.district_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="District not found or not active")

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


# ------------------------------------------------------------------
# Admin — gestión de usuarios
# ------------------------------------------------------------------

@admin_router.get("/users", response_model=list[UserOut])
async def admin_list_users(
    role: Optional[str] = Query(None, description="Filtrar por rol: user|groomer|admin"),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> list[UserOut]:
    """Lista todos los usuarios con filtro opcional por rol."""
    users = await repo.list_by_role(role=role)
    return [_user_to_out(u) for u in users]


@admin_router.get("/users/search", response_model=list[UserSearchResultOut])
async def admin_search_users(
    q: str = Query(..., min_length=3, description="Busca por nombre o apellido"),
    role: Optional[str] = Query("user", description="Filtrar por rol: user|groomer|admin"),
    limit: int = Query(default=20, ge=1, le=50),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> list[UserSearchResultOut]:
    """
    Combobox de búsqueda de dueños (para la pantalla de historial clínico): busca por
    first_name/last_name, enfocado en clientes (role=user por defecto).
    """
    users = await repo.search_by_name(query=q, role=role, limit=limit)
    return [
        UserSearchResultOut(
            id=u.id, first_name=u.first_name, last_name=u.last_name, phone=u.phone, email=u.email,
        )
        for u in users
    ]


@admin_router.patch("/users/{user_id}/role", response_model=UserOut)
async def admin_change_role(
    user_id: UUID,
    payload: ChangeRoleIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresUserRepository = Depends(get_user_repo),
) -> UserOut:
    """Cambia el rol de un usuario (user ↔ groomer ↔ admin)."""
    user = await ChangeUserRole(repo=repo).execute(user_id=user_id, role=payload.role)
    return _user_to_out(user)


@admin_router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    payload: AdminCreateUserIn,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: UserRepository = Depends(get_user_repo),
) -> UserOut:
    """Crea un usuario con el rol especificado (user, groomer o admin)."""
    try:
        user = await RegisterUser(repo=repo, buscar_datos_oficiales=buscar_datos_oficiales).execute(
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
            profile_photo_url=None,  # managed exclusively via POST /media/confirm-profile-photo
        )
    except HTTPException:
        raise
    return _user_to_out(user)


# ---------------------------------------------------------------------------
# Consulta de DNI para autocompletar (feature 0027). Límites y caché en memoria del proceso.
# ---------------------------------------------------------------------------

LIMITES_CONSULTA_DNI = LimitesConsultaDni(
    por_hora=settings.DNI_CONSULTAS_POR_HORA, distintos_por_dia=settings.DNI_DISTINTOS_POR_DIA
)
CACHE_DNI = CacheDni(duracion=settings.DNI_CACHE_HORAS * 3600)


def buscar_datos_oficiales(dni: str) -> Optional[DatosDni]:
    """Datos oficiales de un DNI que el servidor ya consultó (caché de la consulta). Fuente de los nombres legales."""
    return CACHE_DNI.obtener(dni)


@router.post("/users/me/dni/consulta", response_model=DniConsultaOut)
async def consultar_dni(
    payload: DniConsultaIn,
    current: CurrentUser = Depends(get_current_user),
    consultor: ConsultorDni = Depends(obtener_consultor_dni),
) -> DniConsultaOut:
    """Nombres y apellidos de un DNI para autocompletar el perfil del propio cliente.

    No es un buscador: requiere sesión de cliente y tiene límites por usuario (429 con Retry-After). Consultar un DNI no
    prueba titularidad. Mientras Datos Perú no exponga su consulta para clientes, responde 503.
    """
    if current.role != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "DNI_LOOKUP_FORBIDDEN", "message": "La consulta de DNI es solo para completar tu perfil."},
        )
    try:
        datos = await ConsultarDni(consultor=consultor, limites=LIMITES_CONSULTA_DNI, cache=CACHE_DNI).execute(
            current.id, payload.dni
        )
    except LimiteConsultaDni as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "DNI_LOOKUP_RATE_LIMITED", "message": str(error), "retry_after": error.reintentar_en},
            headers={"Retry-After": str(error.reintentar_en)},
        ) from error
    except ConsultaDniLimitada as error:
        # Límite de Datos Perú (no del usuario): mismo código y se conserva su Retry-After.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "DNI_LOOKUP_RATE_LIMITED", "message": str(error), "retry_after": error.reintentar_en},
            headers={"Retry-After": str(error.reintentar_en)},
        ) from error
    except DniNoEncontrado as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DNI_NOT_FOUND", "message": "No encontramos ese DNI. Puedes escribir tus datos a mano."},
        ) from error
    except ConsultaDniNoDisponible as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DNI_LOOKUP_UNAVAILABLE",
                "message": "La consulta de DNI no está disponible ahora. Puedes escribir tus datos a mano.",
            },
        ) from error
    return DniConsultaOut(dni=payload.dni, nombres=datos.nombres, apellidos=datos.apellidos)

