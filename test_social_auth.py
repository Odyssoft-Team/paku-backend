#!/usr/bin/env python3
"""
Test de integración para social auth.
Ejecutar en el contenedor:
  docker compose exec paku-backend python test_social_auth.py
"""
import asyncio
import json
import os

import httpx
import firebase_admin
from firebase_admin import auth as firebase_auth

# ── Config ──────────────────────────────────────────────────────────────────
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "REEMPLAZA_CON_TU_WEB_API_KEY")
BACKEND_URL = "http://localhost:8000"
TEST_EMAIL = "test-social@paku-integration.internal"
TEST_PASSWORD = "PakuTest2024!"
# ────────────────────────────────────────────────────────────────────────────


def init_firebase():
    if not firebase_admin._apps:
        firebase_admin.initialize_app()


def create_or_get_test_user():
    try:
        user = firebase_auth.get_user_by_email(TEST_EMAIL)
        print(f"  ✓ Usuario de test ya existe: {user.uid}")
        return user
    except firebase_admin.auth.UserNotFoundError:
        user = firebase_auth.create_user(
            email=TEST_EMAIL,
            password=TEST_PASSWORD,
            display_name="Test Social User",
            email_verified=True,
        )
        print(f"  ✓ Usuario de test creado: {user.uid}")
        return user


async def get_id_token(api_key: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "returnSecureToken": True},
            timeout=10,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Firebase REST error: {resp.text}")
        data = resp.json()
        print(f"  ✓ ID Token obtenido (expira en {data['expiresIn']}s)")
        return data["idToken"]


async def post_social(id_token: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/auth/social",
            json={"id_token": id_token},
            timeout=10,
        )
        return resp.status_code, resp.json()


async def get_me(access_token: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BACKEND_URL}/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        return resp.status_code, resp.json()


async def put_complete_profile(access_token: str):
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{BACKEND_URL}/users/me/complete",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"phone": "+51987654321", "sex": "M", "birth_date": "1990-05-20"},
            timeout=10,
        )
        return resp.status_code, resp.json()


def cleanup(user):
    firebase_auth.delete_user(user.uid)
    print(f"\n  ✓ Usuario de test eliminado de Firebase: {user.uid}")


async def main():
    print("=" * 55)
    print("  Paku — Social Auth Integration Test")
    print("=" * 55)

    # 1. Firebase
    print("\n[1] Inicializando Firebase (ADC)...")
    init_firebase()
    print("  ✓ Firebase OK")

    # 2. Test user en Firebase
    print("\n[2] Preparando usuario de test en Firebase...")
    user = create_or_get_test_user()

    # 3. ID Token vía REST
    print("\n[3] Obteniendo Firebase ID Token...")
    try:
        id_token = await get_id_token(FIREBASE_API_KEY)
    except RuntimeError as e:
        print(f"  ✗ {e}")
        print("  → Verifica que Email/Password esté habilitado en Firebase Console")
        print("  → Verifica que FIREBASE_API_KEY sea correcto")
        cleanup(user)
        return

    # 4. POST /auth/social — primera vez (is_new_user=True)
    print("\n[4] POST /auth/social (primera vez)...")
    status, body = await post_social(id_token)
    print(f"  Status: {status}")
    print(f"  Body:   {json.dumps(body, indent=4)}")

    if status != 200:
        print("  ✗ Falló /auth/social")
        cleanup(user)
        return

    assert body["is_new_user"] is True, "Esperaba is_new_user=True en primer login"
    print("  ✓ is_new_user=True  ✓")
    access_token = body["access_token"]

    # 5. GET /users/me con token nuevo
    print("\n[5] GET /users/me (perfil incompleto)...")
    status, body = await get_me(access_token)
    print(f"  Status: {status}")
    print(f"  profile_completed: {body.get('profile_completed')}")
    assert body.get("profile_completed") is False, "Esperaba profile_completed=False"
    print("  ✓ profile_completed=False  ✓")

    # 6. PUT /users/me/complete
    print("\n[6] PUT /users/me/complete...")
    status, body = await put_complete_profile(access_token)
    print(f"  Status: {status}")
    print(f"  Body:   {json.dumps(body, indent=4)}")
    assert status == 200
    assert "access_token" in body, "Esperaba nuevos tokens en la respuesta"
    new_token = body["access_token"]
    print("  ✓ Nuevos tokens recibidos  ✓")

    # 7. GET /users/me con token nuevo (profile_completed=True)
    print("\n[7] GET /users/me con nuevo token (perfil completo)...")
    status, body = await get_me(new_token)
    print(f"  Status: {status}")
    print(f"  profile_completed: {body.get('profile_completed')}")
    assert body.get("profile_completed") is True, "Esperaba profile_completed=True"
    print("  ✓ profile_completed=True  ✓")

    # 8. POST /auth/social — segunda vez (is_new_user=False)
    print("\n[8] POST /auth/social (segunda vez, mismo usuario)...")
    status, body = await post_social(id_token)
    print(f"  Status: {status}")
    print(f"  is_new_user: {body.get('is_new_user')}")
    assert body["is_new_user"] is False, "Esperaba is_new_user=False en segundo login"
    print("  ✓ is_new_user=False  ✓")

    print("\n" + "=" * 55)
    print("  ✅  TODOS LOS PASOS OK — Social Auth funcionando")
    print("=" * 55)

    cleanup(user)


if __name__ == "__main__":
    asyncio.run(main())
