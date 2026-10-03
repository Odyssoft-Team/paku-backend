"""Acceso a datos de una mascota: GET /pets/{id} y cotización de store con ?pet_id=."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.auth import CurrentUser
from app.modules.pets.app.use_cases import GetPet
from app.modules.store.app.use_cases_impl.access import check_pet_access


class _FakePetsRepo:
    def __init__(self, pet):
        self.pet = pet

    async def get_by_id(self, pet_id, include_deleted: bool = False):
        return self.pet if self.pet is not None and self.pet.id == pet_id else None


class _FakeOrdersRepo:
    def __init__(self, assigned: bool):
        self.assigned = assigned

    async def is_groomer_assigned_to_pet(self, *, groomer_id, pet_id):
        return self.assigned


def _pet():
    return SimpleNamespace(id=uuid4(), owner_id=uuid4())


def _user(role="user", id=None):
    return CurrentUser(id=id or uuid4(), email="x@example.com", role=role, is_active=True)


# --- GET /pets/{id} -------------------------------------------------------

@pytest.mark.parametrize("who", ["owner", "admin", "assigned_groomer"])
def test_get_pet_allowed(who):
    pet = _pet()
    requester_id = pet.owner_id if who == "owner" else uuid4()
    role = {"owner": "user", "admin": "admin", "assigned_groomer": "groomer"}[who]
    use_case = GetPet(repo=_FakePetsRepo(pet), orders_repo=_FakeOrdersRepo(assigned=True))

    out = asyncio.run(use_case.execute(pet.id, requester_id=requester_id, requester_role=role))

    assert out is pet


@pytest.mark.parametrize("role", ["user", "groomer"])
def test_get_pet_forbidden_for_strangers_and_unassigned_groomers(role):
    pet = _pet()
    use_case = GetPet(repo=_FakePetsRepo(pet), orders_repo=_FakeOrdersRepo(assigned=False))

    with pytest.raises(HTTPException) as err:
        asyncio.run(use_case.execute(pet.id, requester_id=uuid4(), requester_role=role))

    assert err.value.status_code == 403


def test_get_pet_missing_returns_404():
    use_case = GetPet(repo=_FakePetsRepo(None), orders_repo=_FakeOrdersRepo(assigned=True))

    with pytest.raises(HTTPException) as err:
        asyncio.run(use_case.execute(uuid4(), requester_id=uuid4(), requester_role="admin"))

    assert err.value.status_code == 404


# --- store con ?pet_id= ---------------------------------------------------

def test_store_without_pet_id_stays_public():
    asyncio.run(check_pet_access(None, None, _FakePetsRepo(None)))


def test_store_pet_id_requires_session():
    with pytest.raises(HTTPException) as err:
        asyncio.run(check_pet_access(uuid4(), None, _FakePetsRepo(None)))
    assert err.value.status_code == 401


def test_store_pet_id_owner_ok_stranger_403():
    pet = _pet()
    repo = _FakePetsRepo(pet)

    asyncio.run(check_pet_access(pet.id, _user(id=pet.owner_id), repo))

    with pytest.raises(HTTPException) as err:
        asyncio.run(check_pet_access(pet.id, _user(), repo))
    assert err.value.status_code == 403


def test_store_pet_id_admin_ok():
    asyncio.run(check_pet_access(uuid4(), _user(role="admin"), _FakePetsRepo(None)))
