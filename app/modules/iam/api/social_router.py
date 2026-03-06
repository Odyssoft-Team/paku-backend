from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, create_access_token, create_refresh_token, get_current_user
from app.core.db import engine, get_async_session
from app.modules.iam.api.schemas import (
    CompleteProfileIn,
    LinkedIdentityOut,
    LinkSocialIn,
    SetPasswordIn,
    SocialLoginIn,
    SocialTokenOut,
    UserOut,
)
from app.modules.iam.app.use_cases_impl.account_linking import AddPassword, LinkSocialIdentity
from app.modules.iam.app.use_cases_impl.profile import CompleteProfile
from app.modules.iam.app.use_cases_impl.social_auth import SocialLogin
from app.modules.iam.domain.user import Sex, UserRepository
from app.modules.iam.infra.firebase_provider import FirebaseOAuthProvider
from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository
from app.modules.iam.infra.social_repository import PostgresSocialIdentityRepository

router = APIRouter(tags=["iam-social"])


def get_user_repo(session: AsyncSession = Depends(get_async_session)) -> UserRepository:
    return PostgresUserRepository(session=session, engine=engine)


def get_social_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresSocialIdentityRepository:
    return PostgresSocialIdentityRepository(session=session)


@router.post("/auth/social", response_model=SocialTokenOut)
async def social_login(
    payload: SocialLoginIn,
    repo: UserRepository = Depends(get_user_repo),
    social_repo: PostgresSocialIdentityRepository = Depends(get_social_repo),
) -> SocialTokenOut:
    """Autentica o registra un usuario usando un Firebase ID Token.

    El móvil autentica con Google, Apple o Facebook vía Firebase SDK,
    obtiene el ID Token y lo envía aquí. El backend lo verifica, identifica
    o crea el usuario local y emite sus propios JWT.

    - `is_new_user: true` → perfil incompleto, redirigir a PUT /users/me/complete
    - `is_new_user: false` → sesión lista
    """
    oauth_provider = FirebaseOAuthProvider()
    user, is_new_user = await SocialLogin(
        repo=repo,
        social_repo=social_repo,
        oauth_provider=oauth_provider,
    ).execute(id_token=payload.id_token)

    return SocialTokenOut(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        is_new_user=is_new_user,
    )


@router.put("/users/me/complete", response_model=SocialTokenOut)
async def complete_profile(
    payload: CompleteProfileIn,
    current: CurrentUser = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
) -> SocialTokenOut:
    """Completa el perfil de un usuario registrado vía social login.

    Solo necesario cuando is_new_user=true en /auth/social.
    Recibe phone, sex y birth_date — datos que los proveedores sociales no entregan.
    Devuelve nuevos tokens con profile_completed=true para que el guard no bloquee futuros requests.
    """
    user = await CompleteProfile(repo=repo).execute(
        user_id=current.id,
        phone=payload.phone,
        sex=Sex(payload.sex),
        birth_date=payload.birth_date,
        dni=payload.dni,
    )
    return SocialTokenOut(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        is_new_user=False,
    )


@router.put("/users/me/password", response_model=UserOut, status_code=status.HTTP_200_OK)
async def set_password(
    payload: SetPasswordIn,
    current: CurrentUser = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
) -> UserOut:
    """Agrega o cambia la contraseña del usuario autenticado.

    - Cuenta social (sin contraseña): solo enviar new_password.
    - Cuenta con contraseña existente: enviar current_password + new_password.
    """
    user = await AddPassword(repo=repo).execute(
        user_id=current.id,
        new_password=payload.new_password,
        current_password=payload.current_password,
    )
    return UserOut(**user.__dict__)


@router.post("/users/me/link-social", response_model=LinkedIdentityOut, status_code=status.HTTP_200_OK)
async def link_social(
    payload: LinkSocialIn,
    current: CurrentUser = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
    social_repo: PostgresSocialIdentityRepository = Depends(get_social_repo),
) -> LinkedIdentityOut:
    """Vincula una identidad social (Google/Apple/Facebook) a la cuenta actual.

    El cliente autentica con Firebase, obtiene el ID Token y lo envía aquí.
    El backend verifica el token y crea el vínculo en user_social_identities.
    Idempotente: si ya está vinculado al mismo usuario, devuelve el vínculo existente.
    """
    oauth_provider = FirebaseOAuthProvider()
    identity = await LinkSocialIdentity(
        repo=repo,
        social_repo=social_repo,
        oauth_provider=oauth_provider,
    ).execute(user_id=current.id, id_token=payload.id_token)

    return LinkedIdentityOut(
        id=identity.id,
        provider=identity.provider,
        created_at=identity.created_at,
    )
