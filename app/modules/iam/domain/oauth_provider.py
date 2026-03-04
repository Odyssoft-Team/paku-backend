from typing import Optional, Protocol, TypedDict


class OAuthProfile(TypedDict):
    """Perfil normalizado devuelto por cualquier proveedor OAuth."""
    email: str
    provider_user_id: str       # firebase uid
    display_name: str           # nombre completo del proveedor
    photo_url: Optional[str]    # foto de perfil del proveedor
    sign_in_provider: str       # "google.com" | "apple.com" | "facebook.com"


class OAuthProvider(Protocol):
    async def exchange_token(self, provider: str, token: str) -> OAuthProfile:
        ...
