from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.core.auth import create_access_token, create_refresh_token, hash_password
from app.modules.iam.domain.user import Role, User, UserRepository


@dataclass
class RegisterUser:
    repo: UserRepository

    async def execute(self, email: str, password: str, role: Role = "user") -> User:
        existing = await self.repo.get_by_email(email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user = User.new(email=email, password_hash=hash_password(password), role=role)
        await self.repo.add(user)
        return user


@dataclass
class LoginUser:
    repo: UserRepository

    async def execute(self, email: str, password: str) -> dict:
        user = await self.repo.get_by_email(email)
        if not user or user.password_hash != hash_password(password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )
        return {
            "access_token": create_access_token(user),
            "refresh_token": create_refresh_token(user),
            "token_type": "bearer",
        }


@dataclass
class GetMe:
    repo: UserRepository

    async def execute(self, user_id: UUID) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
