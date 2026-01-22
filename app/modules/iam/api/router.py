from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, create_access_token, decode_token, get_current_user
from app.modules.iam.api.schemas import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from app.modules.iam.app.use_cases import GetMe, LoginUser, RegisterUser
from app.modules.iam.infra.user_repository import InMemoryUserRepository

router = APIRouter(tags=["iam"])
_repo = InMemoryUserRepository()


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn) -> UserOut:
    user = await RegisterUser(repo=_repo).execute(
        email=payload.email, password=payload.password, role=payload.role
    )
    return UserOut(**user.__dict__)


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn) -> TokenOut:
    tokens = await LoginUser(repo=_repo).execute(email=payload.email, password=payload.password)
    return TokenOut(**tokens)


@router.post("/auth/refresh", response_model=TokenOut)
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
async def me(current: CurrentUser = Depends(get_current_user)) -> UserOut:
    user = await GetMe(repo=_repo).execute(user_id=current.id)
    return UserOut(**user.__dict__)
