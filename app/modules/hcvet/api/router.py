"""Integración con HCVet (feature 0028): consentimientos del cliente, estado del vínculo y cola de operaciones.

Estas rutas no llaman a HCVet: guardan en Paku y encolan. Responden igual con HCVet caído.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import get_async_session
from app.core.settings import settings
from app.modules.hcvet.api.schemas import DecisionesIn, EstadoHcvetOut, OperacionOut
from app.modules.hcvet.app.servicio import ProcesadorHcvet, ServicioIntegracionHcvet, UsuarioNoEncontrado
from app.modules.hcvet.domain import sincronizacion as s
from app.modules.hcvet.domain.consentimientos import Decision, DecisionInvalida, VersionDeTextoDesactualizada
from app.modules.hcvet.infra.cliente import cliente_desde_settings
from app.modules.hcvet.infra.repositorio import PostgresRepositorioHcvet, RepositorioHcvet

router = APIRouter(tags=["hcvet"])
admin_router = APIRouter(tags=["hcvet-admin"])
admin_only = require_roles("admin")


def obtener_repositorio_hcvet(session: AsyncSession = Depends(get_async_session)) -> RepositorioHcvet:
    return PostgresRepositorioHcvet(session)


def _servicio(repo: RepositorioHcvet) -> ServicioIntegracionHcvet:
    return ServicioIntegracionHcvet(repo, activa=settings.HCVET_INTEGRACION_ACTIVA)


def _solo_clientes(current: CurrentUser) -> None:
    if current.role != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "HCVET_ONLY_CLIENTS", "message": "La integración con HCVet es para clientes."},
        )


def _ip(request: Request) -> Optional[str]:
    reenviada = request.headers.get("X-Forwarded-For")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/users/me/hcvet", response_model=EstadoHcvetOut)
async def estado_hcvet(
    current: CurrentUser = Depends(get_current_user),
    repo: RepositorioHcvet = Depends(obtener_repositorio_hcvet),
) -> dict:
    """Consentimientos (con el texto vigente y la última decisión) y estado del vínculo con HCVet.

    ``vinculado`` solo cuando HCVet lo confirmó, con ``acceso`` ``completo`` o ``basico`` (vinculado a un propietario
    que ya existía: sin acceso a sus mascotas e historiales previos hasta que el dueño lo amplíe, con su sesión en
    HCVet o por medio de otra plataforma que ya tenga su autorización; nunca Paku a sí mismo, HCVet D-106).
    """
    _solo_clientes(current)
    return await _servicio(repo).estado(current.id)


@router.put("/users/me/hcvet/consentimientos", response_model=EstadoHcvetOut)
async def decidir_consentimientos(
    payload: DecisionesIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    repo: RepositorioHcvet = Depends(obtener_repositorio_hcvet),
) -> dict:
    """Registra decisiones explícitas (concede o rechaza) con evidencia. Rechazar no limita los servicios de Paku."""
    _solo_clientes(current)
    try:
        return await _servicio(repo).decidir(
            current.id,
            [Decision(d.tipo, d.concedido, d.version_texto) for d in payload.decisiones],
            canal=payload.canal,
            ip=_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
    except VersionDeTextoDesactualizada as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "CONSENT_TEXT_OUTDATED", "message": str(error)}) from error
    except DecisionInvalida as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"code": "CONSENT_INVALID", "message": str(error)}) from error
    except UsuarioNoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error


@admin_router.get("/hcvet/operaciones", response_model=list[OperacionOut])
async def listar_operaciones(
    estado: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: CurrentUser = Depends(admin_only),
    repo: RepositorioHcvet = Depends(obtener_repositorio_hcvet),
) -> list:
    """Cola de sincronización con HCVet (sin datos personales: solo ids, estados y errores saneados)."""
    if estado is not None and estado not in s.ESTADOS_OPERACION:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Estado desconocido.")
    return await repo.listar_operaciones(estado, limit)


@admin_router.post("/hcvet/operaciones/{op_id}/reintentar", response_model=OperacionOut)
async def reintentar_operacion(
    op_id: UUID,
    _: CurrentUser = Depends(admin_only),
    repo: RepositorioHcvet = Depends(obtener_repositorio_hcvet),
):
    """Vuelve a encolar una operación fallida, en conflicto o bloqueada (p. ej., tras corregir la API Key)."""
    op = await ProcesadorHcvet(repo, cliente_desde_settings(), activa=settings.HCVET_INTEGRACION_ACTIVA).reintentar(op_id)
    if op is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operación no encontrada.")
    return op
