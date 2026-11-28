from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.auth import hash_password
from app.core.settings import settings
from app.modules.iam.domain.dni import DatosDni
from app.modules.iam.domain.user import (
    Address,
    DatosLegales,
    DniYaRegistrado,
    Role,
    Sex,
    User,
    UserRepository,
    has_required_profile,
)

# Busca los datos oficiales de un DNI que el servidor ya consultó (caché de la consulta de DNI). None si no hay.
BuscarDatosOficiales = Callable[[str], Optional[DatosDni]]


def exigir_dni_si_corresponde(role: str, dni: Optional[str]) -> None:
    """Con DNI_OBLIGATORIO, un cliente (rol user) necesita DNI para completar su perfil (feature 0027)."""
    if settings.DNI_OBLIGATORIO and role == "user" and not dni:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "DNI_REQUIRED", "message": "Ingresa tu DNI para completar tu perfil."},
        )


async def verificar_dni_disponible(repo: UserRepository, dni: Optional[str], propio_id: Optional[UUID]) -> None:
    """Un DNI no puede estar en dos cuentas. No revela cuál lo tiene ni fusiona cuentas (REQUIREMENTS §4.4)."""
    if not dni:
        return
    otro = await repo.get_by_dni(dni)
    if otro is not None and otro.id != propio_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DNI_ALREADY_REGISTERED",
                "message": "Este DNI ya está registrado en otra cuenta. Si es tuyo, contáctanos para revisarlo.",
            },
        )


def datos_legales_para(
    actual: Optional[User], dni_final: Optional[str], buscar: Optional[BuscarDatosOficiales]
) -> Optional[DatosLegales]:
    """Nombres legales que corresponden al DNI que queda en la cuenta (feature 0027).

    - Solo salen de una consulta hecha por el servidor (``buscar``), nunca de lo que envía el cliente.
    - Si el DNI cambia y no hay consulta de ese DNI, se borran: eran de otro DNI.
    - No es verificación de titularidad.
    """
    previos = actual.datos_legales if actual is not None and actual.dni == dni_final else None
    if not dni_final or buscar is None:
        return previos
    oficiales = buscar(dni_final)
    if oficiales is None:
        return previos
    return DatosLegales(
        nombres=oficiales.nombres,
        apellidos=oficiales.apellidos,
        fuente=oficiales.fuente,
        consultado_en=datetime.now(timezone.utc),
    )


_DNI_YA_REGISTRADO = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={
        "code": "DNI_ALREADY_REGISTERED",
        "message": "Este DNI ya está registrado en otra cuenta. Si es tuyo, contáctanos para revisarlo.",
    },
)


async def guardar_con_dni_unico(operacion) -> None:
    """Ejecuta add/update; si el índice único de DNI lo rechaza (carrera entre dos cuentas), responde 409."""
    try:
        await operacion
    except DniYaRegistrado as error:
        raise HTTPException(status_code=_DNI_YA_REGISTRADO.status_code, detail=_DNI_YA_REGISTRADO.detail) from error


@dataclass
class RegisterUser:
    repo: UserRepository
    buscar_datos_oficiales: Optional[BuscarDatosOficiales] = None

    async def execute(
        self,
        email: str,
        password: str,
        phone: str,
        first_name: str,
        last_name: str,
        sex: Sex,
        birth_date: date,
        role: Role = "user",
        dni: Optional[str] = None,
        address: Optional[Address] = None,
        profile_photo_url: Optional[str] = None,
    ) -> User:
        existing = await self.repo.get_by_email(email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        exigir_dni_si_corresponde(role, dni)
        await verificar_dni_disponible(self.repo, dni, propio_id=None)
        user = User.new(
            email=email,
            password_hash=hash_password(password),
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            birth_date=birth_date,
            role=role,
            dni=dni,
            address=address,
            profile_photo_url=profile_photo_url,
        )
        legales = datos_legales_para(None, dni, self.buscar_datos_oficiales)
        if legales is not None:
            user = replace(user, datos_legales=legales)
        await guardar_con_dni_unico(self.repo.add(user))
        return user


@dataclass
class GetMe:
    repo: UserRepository

    async def execute(self, user_id: UUID) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user


@dataclass
class UpdateProfile:
    repo: UserRepository
    buscar_datos_oficiales: Optional[BuscarDatosOficiales] = None

    async def execute(
        self,
        user_id: UUID,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        sex: Optional[Sex] = None,
        birth_date: Optional[date] = None,
        dni: Optional[str] = None,
        address: Optional[Address] = None,
        profile_photo_url: Optional[str] = None,
    ) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        await verificar_dni_disponible(self.repo, dni, propio_id=user.id)

        new_phone = phone if phone is not None else user.phone
        new_sex = sex if sex is not None else user.sex
        new_birth = birth_date if birth_date is not None else user.birth_date
        updated = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            phone=new_phone,
            first_name=first_name if first_name is not None else user.first_name,
            last_name=last_name if last_name is not None else user.last_name,
            sex=new_sex,
            birth_date=new_birth,
            # Nunca vuelve a incompleto; se completa al tener teléfono, sexo y fecha de nacimiento (desde «Mi perfil»,
            # no solo con PUT /users/me/complete)
            profile_completed=user.profile_completed or has_required_profile(
                SimpleNamespace(phone=new_phone, sex=new_sex, birth_date=new_birth)),
            dni=dni if dni is not None else user.dni,
            address=address if address is not None else user.address,
            profile_photo_url=profile_photo_url
            if profile_photo_url is not None
            else user.profile_photo_url,
            datos_legales=datos_legales_para(
                user, dni if dni is not None else user.dni, self.buscar_datos_oficiales),
        )
        await guardar_con_dni_unico(self.repo.update(updated))
        return updated


@dataclass
class ChangeUserRole:
    """Cambia el rol de un usuario. Solo ejecutable por admins."""

    repo: UserRepository

    async def execute(self, user_id: UUID, role: Role) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        updated = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=role,
            is_active=user.is_active,
            created_at=user.created_at,
            phone=user.phone,
            first_name=user.first_name,
            last_name=user.last_name,
            sex=user.sex,
            birth_date=user.birth_date,
            profile_completed=user.profile_completed,
            dni=user.dni,
            address=user.address,
            datos_legales=user.datos_legales,
            profile_photo_url=user.profile_photo_url,
        )
        await self.repo.update(updated)
        return updated


@dataclass
class CompleteProfile:
    """Completa el perfil de un usuario social (Google/Apple/Facebook).
    Recibe los campos obligatorios que el proveedor no entregó y marca profile_completed=True.
    """

    repo: UserRepository
    buscar_datos_oficiales: Optional[BuscarDatosOficiales] = None

    async def execute(
        self,
        user_id: UUID,
        phone: str,
        sex: Sex,
        birth_date: date,
        dni: Optional[str] = None,
    ) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        exigir_dni_si_corresponde(user.role, dni if dni is not None else user.dni)
        await verificar_dni_disponible(self.repo, dni, propio_id=user.id)

        updated = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_photo_url=user.profile_photo_url,
            phone=phone,
            sex=sex,
            birth_date=birth_date,
            profile_completed=True,
            dni=dni if dni is not None else user.dni,
            address=user.address,
            datos_legales=datos_legales_para(
                user, dni if dni is not None else user.dni, self.buscar_datos_oficiales),
        )
        await guardar_con_dni_unico(self.repo.update(updated))
        return updated
