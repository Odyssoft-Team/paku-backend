"""Tokens emitidos antes del renombre ally → groomer siguen funcionando como groomer."""
import asyncio
from uuid import uuid4

from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import create_access_token, get_current_user, normalize_role


def test_normalize_role_maps_legacy_ally():
    assert normalize_role("ally") == "groomer"
    assert normalize_role("groomer") == "groomer"
    assert normalize_role("admin") == "admin"


def test_access_token_with_legacy_role_is_read_as_groomer():
    token = create_access_token(user_id=uuid4(), email="g@example.com", role="ally")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    current = asyncio.run(get_current_user(credentials=creds, request=None))

    assert current.role == "groomer"
