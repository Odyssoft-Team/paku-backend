from typing import Protocol, TypedDict


class OAuthProfile(TypedDict):
    email: str
    provider_user_id: str


class OAuthProvider(Protocol):
    async def exchange_token(self, provider: str, token: str) -> OAuthProfile:
        ...


class NotImplementedOAuthProvider:
    async def exchange_token(self, provider: str, token: str) -> OAuthProfile:
        raise NotImplementedError()
