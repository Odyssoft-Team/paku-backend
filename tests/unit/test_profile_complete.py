"""Perfil completo para reservar: un usuario de login social que completa teléfono, sexo y fecha de nacimiento en «Mi
perfil» (PUT /users/me) queda completo y puede reservar sin volver a iniciar sesión."""
import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core import auth
from app.core.auth import CurrentUser, require_profile_complete
from app.modules.iam.app.use_cases_impl.profile import UpdateProfile
from app.modules.iam.domain.user import Sex, User, has_required_profile


class _Repo:
    def __init__(self, user):
        self.user = user

    async def get_by_id(self, user_id):
        return self.user

    async def update(self, user):
        self.user = user


def _social_user() -> User:
    return User.new_social(email="ana@gmail.com", first_name="Ana", last_name="Pérez")


def test_has_required_profile():
    assert has_required_profile(SimpleNamespace(phone="999888777", sex=Sex.female, birth_date=date(1990, 1, 1)))
    assert not has_required_profile(SimpleNamespace(phone="  ", sex=Sex.female, birth_date=date(1990, 1, 1)))
    assert not has_required_profile(SimpleNamespace(phone="999", sex=None, birth_date=date(1990, 1, 1)))
    assert not has_required_profile(SimpleNamespace(phone="999", sex=Sex.male, birth_date=None))


def test_update_profile_completes_when_the_three_fields_are_present():
    repo = _Repo(_social_user())
    assert repo.user.profile_completed is False
    asyncio.run(UpdateProfile(repo=repo).execute(repo.user.id, phone="999888777"))
    assert repo.user.profile_completed is False                # le faltan sexo y fecha
    asyncio.run(UpdateProfile(repo=repo).execute(repo.user.id, sex=Sex.female, birth_date=date(1990, 1, 1)))
    assert repo.user.profile_completed is True
    asyncio.run(UpdateProfile(repo=repo).execute(repo.user.id, first_name="Ana María"))
    assert repo.user.profile_completed is True                 # nunca vuelve a incompleto


def test_booking_guard_checks_the_database_when_the_token_is_stale(monkeypatch):
    guard = require_profile_complete()
    stale = CurrentUser(id=uuid4(), email="ana@gmail.com", role="user", is_active=True, profile_completed=False)

    async def complete(_):
        return True

    async def incomplete(_):
        return False

    monkeypatch.setattr(auth, "profile_complete_in_db", complete)
    assert asyncio.run(guard(current=stale)) is stale

    monkeypatch.setattr(auth, "profile_complete_in_db", incomplete)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(guard(current=stale))
    assert exc.value.status_code == 403 and exc.value.detail["code"] == "PROFILE_INCOMPLETE"

    fresh = CurrentUser(id=uuid4(), email="b@b.pe", role="user", is_active=True, profile_completed=True)
    assert asyncio.run(guard(current=fresh)) is fresh       # con el token al día no consulta la base
