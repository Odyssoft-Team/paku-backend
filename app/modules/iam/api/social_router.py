from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, create_access_token, create_refresh_token, get_current_user
from app.core.db import engine, get_async_session
from app.modules.iam.api.schemas import CompleteProfileIn, SocialLoginIn, SocialTokenOut
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
