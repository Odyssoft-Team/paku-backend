from typing import Dict, Optional
from uuid import UUID

from app.modules.iam.domain.user import User, UserRepository


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self._by_id: Dict[UUID, User] = {}
        self._by_email: Dict[str, UUID] = {}

    async def get_by_email(self, email: str) -> Optional[User]:
        user_id = self._by_email.get(email.strip().lower())
        if not user_id:
            return None
        return self._by_id.get(user_id)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        return self._by_id.get(user_id)

    async def add(self, user: User) -> None:
        email = user.email.strip().lower()
        if email in self._by_email:
            raise ValueError("email_exists")
        self._by_id[user.id] = user
        self._by_email[email] = user.id

    async def update(self, user: User) -> None:
        if user.id not in self._by_id:
            raise ValueError("user_not_found")
        self._by_id[user.id] = user
