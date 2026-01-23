from typing import Protocol, TypedDict


# [TECH]
# TypedDict describing the minimal user profile returned by an external OAuth provider.
# Inputs: email and provider_user_id (provider-specific identifier).
# Output: normalized mapping used by IAM to link or create users.
# Flow: would be part of a social-login flow (not implemented in this project).
#
# [BUSINESS]
# Perfil básico que vendría de un proveedor externo (por ejemplo Google/Apple).
# Permite identificar al usuario por su correo y por el ID que el proveedor le asigna.
class OAuthProfile(TypedDict):
    email: str
    provider_user_id: str


# [TECH]
# Interface for OAuth provider integrations.
# Method: exchange_token(provider, token) returns an OAuthProfile.
# Flow: authentication via third-party providers (placeholder here).
#
# [BUSINESS]
# Contrato para integrar inicios de sesión con servicios externos.
# Permitiría que el usuario ingrese con un token de un proveedor (ej. Google).
class OAuthProvider(Protocol):
    async def exchange_token(self, provider: str, token: str) -> OAuthProfile:
        ...


# [TECH]
# Placeholder implementation that signals OAuth is not supported yet.
# Always raises NotImplementedError.
#
# [BUSINESS]
# Implementación vacía: el inicio de sesión con proveedores externos aún no está disponible.
class NotImplementedOAuthProvider:
    async def exchange_token(self, provider: str, token: str) -> OAuthProfile:
        raise NotImplementedError()
