"""Persistencia de la integración con HCVet (feature 0028)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional, Protocol
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hcvet.domain import sincronizacion as s
from app.modules.hcvet.infra.models import HcvetConsentimientoModel, HcvetOperacionModel, HcvetVinculoModel


class RepositorioHcvet(Protocol):
    async def usuario(self, user_id: UUID) -> Any: ...
    async def distrito(self, user_id: UUID) -> Optional[str]: ...
    async def consentimientos(self, user_id: UUID) -> list[HcvetConsentimientoModel]: ...
    async def agregar_consentimiento(self, fila: HcvetConsentimientoModel) -> None: ...
    async def vinculo(self, user_id: UUID, *, bloquear: bool = False) -> Optional[HcvetVinculoModel]: ...
    async def guardar_vinculo(self, vinculo: HcvetVinculoModel) -> None: ...
    async def operaciones(self, user_id: UUID) -> list[HcvetOperacionModel]: ...
    async def agregar_operacion(self, op: HcvetOperacionModel) -> None: ...
    async def guardar_operacion(self, op: HcvetOperacionModel) -> None: ...
    async def operacion(self, op_id: UUID) -> Optional[HcvetOperacionModel]: ...
    async def tomar_vencidas(self, ahora: datetime, limite: int) -> list[HcvetOperacionModel]: ...
    async def listar_operaciones(self, estado: Optional[str], limite: int) -> list[HcvetOperacionModel]: ...
    async def confirmar(self) -> None: ...


def condicion_vencida(ahora: datetime):
    """Operaciones que toca procesar: pendientes, bloqueadas a revisar, fallas temporales vencidas y envíos colgados."""
    colgada = ahora - timedelta(minutes=s.COLGADA_MINUTOS)
    a_tiempo = or_(HcvetOperacionModel.proximo_intento_en.is_(None), HcvetOperacionModel.proximo_intento_en <= ahora)
    return or_(
        and_(HcvetOperacionModel.estado.in_((s.PENDIENTE, s.BLOQUEADO)), a_tiempo),
        and_(HcvetOperacionModel.estado == s.FALLIDO, HcvetOperacionModel.reintentable.is_(True), a_tiempo),
        and_(HcvetOperacionModel.estado == s.SINCRONIZANDO, HcvetOperacionModel.actualizado_en <= colgada),
    )


class PostgresRepositorioHcvet:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def usuario(self, user_id: UUID) -> Any:
        from app.modules.iam.infra.models import UserModel

        return await self.session.get(UserModel, user_id)

    async def distrito(self, user_id: UUID) -> Optional[str]:
        """Nombre del distrito de la dirección principal (o la más reciente); si no hay, el del perfil antiguo."""
        from app.modules.geo.infra.districts_data import get_district_by_id
        from app.modules.iam.infra.models import UserAddressModel, UserModel

        fila = (
            await self.session.execute(
                select(UserAddressModel.district_id)
                .where(UserAddressModel.user_id == user_id, UserAddressModel.deleted_at.is_(None))
                .order_by(UserAddressModel.is_default.desc(), UserAddressModel.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if fila is None:
            usuario = await self.session.get(UserModel, user_id)
            fila = usuario.address_district_id if usuario else None
        distrito = get_district_by_id(fila) if fila else None
        return (distrito or {}).get("name")

    async def consentimientos(self, user_id: UUID) -> list[HcvetConsentimientoModel]:
        resultado = await self.session.execute(
            select(HcvetConsentimientoModel)
            .where(HcvetConsentimientoModel.user_id == user_id)
            .order_by(HcvetConsentimientoModel.registrado_en)
        )
        return list(resultado.scalars())

    async def agregar_consentimiento(self, fila: HcvetConsentimientoModel) -> None:
        self.session.add(fila)

    async def vinculo(self, user_id: UUID, *, bloquear: bool = False) -> Optional[HcvetVinculoModel]:
        consulta = select(HcvetVinculoModel).where(HcvetVinculoModel.user_id == user_id)
        if bloquear:
            consulta = consulta.with_for_update()
        return (await self.session.execute(consulta)).scalar_one_or_none()

    async def guardar_vinculo(self, vinculo: HcvetVinculoModel) -> None:
        self.session.add(vinculo)

    async def operaciones(self, user_id: UUID) -> list[HcvetOperacionModel]:
        resultado = await self.session.execute(
            select(HcvetOperacionModel)
            .where(HcvetOperacionModel.user_id == user_id)
            .order_by(HcvetOperacionModel.creado_en)
        )
        return list(resultado.scalars())

    async def agregar_operacion(self, op: HcvetOperacionModel) -> None:
        self.session.add(op)

    async def guardar_operacion(self, op: HcvetOperacionModel) -> None:
        self.session.add(op)

    async def operacion(self, op_id: UUID) -> Optional[HcvetOperacionModel]:
        return await self.session.get(HcvetOperacionModel, op_id)

    async def tomar_vencidas(self, ahora: datetime, limite: int) -> list[HcvetOperacionModel]:
        """``FOR UPDATE SKIP LOCKED``: dos instancias del backend no toman la misma operación."""
        resultado = await self.session.execute(
            select(HcvetOperacionModel)
            .where(condicion_vencida(ahora))
            .order_by(HcvetOperacionModel.creado_en)
            .limit(limite)
            .with_for_update(skip_locked=True)
        )
        return list(resultado.scalars())

    async def listar_operaciones(self, estado: Optional[str], limite: int) -> list[HcvetOperacionModel]:
        consulta = select(HcvetOperacionModel).order_by(HcvetOperacionModel.creado_en.desc()).limit(limite)
        if estado:
            consulta = consulta.where(HcvetOperacionModel.estado == estado)
        return list((await self.session.execute(consulta)).scalars())

    async def confirmar(self) -> None:
        await self.session.commit()
