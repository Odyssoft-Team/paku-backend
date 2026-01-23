from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, create_access_token, decode_token, get_current_user
from app.modules.iam.api.schemas import AddressOut, LoginIn, RefreshIn, RegisterIn, TokenOut, UpdateProfileIn, UserOut
from app.modules.iam.app.use_cases import GetMe, LoginUser, RegisterUser, UpdateProfile
from app.modules.iam.domain.user import Address, Sex
from app.modules.iam.infra.user_repository import InMemoryUserRepository

router = APIRouter(tags=["iam"])
_repo = InMemoryUserRepository()


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn) -> UserOut:
    address_domain = None
    if payload.address:
        address_domain = Address(
            district_id=payload.address.district_id,
            address_line=payload.address.address_line,
            lat=payload.address.lat,
            lng=payload.address.lng,
        )
    user = await RegisterUser(repo=_repo).execute(
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
async def update_me(payload: UpdateProfileIn, current: CurrentUser = Depends(get_current_user)) -> UserOut:
    address_domain = None
    if payload.address:
        address_domain = Address(
            district_id=payload.address.district_id,
            address_line=payload.address.address_line,
            lat=payload.address.lat,
            lng=payload.address.lng,
        )
    user = await UpdateProfile(repo=_repo).execute(
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
