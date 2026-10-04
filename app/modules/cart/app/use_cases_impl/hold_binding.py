"""
Liga la reserva de cupo (booking) al servicio base del carrito.

Regla de negocio (2026-10-04): el cliente reserva el cupo del día antes de comprar; la reserva queda
bloqueada mientras compra y vence junto con el carrito. Si vence, el cliente debe volver a elegir fecha
(código HOLD_EXPIRED). Al crear la orden se confirma; si la orden se cancela o se salta, se libera.

El servicio base del carrito lleva `meta.hold_id`. La fecha del servicio (`meta.scheduled_date`) sale de
la reserva: si el front la envía, debe coincidir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.booking.domain.hold import Hold, HoldStatus
from app.modules.cart.domain.cart import CartItemKind

from .common import _kind_value, _meta_dict


def _error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})


def hold_expired_error(hold_id: Optional[UUID] = None) -> HTTPException:
    extra = {"hold_id": str(hold_id)} if hold_id else {}
    return _error(
        status.HTTP_409_CONFLICT,
        "HOLD_EXPIRED",
        "La reserva del día venció o ya no está vigente. Elige la fecha de nuevo.",
        **extra,
    )


def base_line(lines: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return next((l for l in lines if _kind_value(l.get("kind")) == CartItemKind.service_base.value), None)


def line_hold_id(line: Optional[dict[str, Any]]) -> Optional[UUID]:
    raw = _meta_dict((line or {}).get("meta")).get("hold_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        raise _error(status.HTTP_400_BAD_REQUEST, "INVALID_HOLD_ID", "meta.hold_id inválido.", value=str(raw))


@dataclass
class CartHolds:
    hold_repo: Any  # PostgresHoldRepository

    async def _get_owned(self, hold_id: UUID, *, user_id: UUID) -> Hold:
        hold = await self.hold_repo.get_hold(hold_id)
        if hold is None:
            raise _error(status.HTTP_404_NOT_FOUND, "HOLD_NOT_FOUND", "Reserva no encontrada.")
        if hold.user_id != user_id:
            raise _error(status.HTTP_403_FORBIDDEN, "HOLD_NOT_OWNED", "La reserva no pertenece al usuario.")
        return hold

    async def bind(self, lines: list[dict[str, Any]], *, user_id: UUID) -> list[dict[str, Any]]:
        """
        Valida la reserva del servicio base y devuelve las líneas con `meta.scheduled_date` tomada de la
        reserva. No cambia la reserva (eso lo hace `attach` cuando el carrito ya se guardó).
        """
        base = base_line(lines)
        if base is None:
            return lines
        hold_id = line_hold_id(base)
        if hold_id is None:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                "HOLD_REQUIRED",
                "Reserva primero el cupo del día (POST /holds) y envía meta.hold_id en el servicio.",
            )
        hold = await self._get_owned(hold_id, user_id=user_id)
        if hold.status != HoldStatus.held:
            raise hold_expired_error(hold_id)

        meta = dict(_meta_dict(base.get("meta")))
        mismatches = []
        if str(hold.service_id) != str(base.get("ref_id")):
            mismatches.append("service")
        if meta.get("pet_id") and str(hold.pet_id) != str(meta.get("pet_id")):
            mismatches.append("pet_id")
        if hold.date is not None and meta.get("scheduled_date") and str(meta["scheduled_date"]) != hold.date.isoformat():
            mismatches.append("scheduled_date")
        if mismatches:
            raise _error(
                status.HTTP_409_CONFLICT,
                "HOLD_MISMATCH",
                "La reserva no corresponde a este servicio, mascota o fecha.",
                fields=mismatches,
            )

        meta.setdefault("pet_id", str(hold.pet_id))
        if hold.date is not None:
            meta["scheduled_date"] = hold.date.isoformat()
        meta["hold_id"] = str(hold.id)

        out = []
        for line in lines:
            out.append({**line, "meta": meta} if line is base else line)
        return out

    async def attach(self, hold_id: Optional[UUID], *, cart_expires_at: datetime) -> None:
        """La reserva vence junto con el carrito."""
        if hold_id is not None:
            await self.hold_repo.set_expiry(hold_id, cart_expires_at)

    async def release(self, hold_id: Optional[UUID]) -> None:
        """Libera una reserva que el carrito dejó de usar (cambio o eliminación del servicio)."""
        if hold_id is not None:
            await self.hold_repo.release(hold_id)

    async def assert_still_valid(self, lines: list[dict[str, Any]], *, user_id: UUID) -> Optional[Hold]:
        """Checkout / creación de orden: la reserva debe seguir vigente."""
        base = base_line(lines)
        if base is None:
            return None
        hold_id = line_hold_id(base)
        if hold_id is None:
            raise _error(
                status.HTTP_400_BAD_REQUEST,
                "HOLD_REQUIRED",
                "El servicio no tiene reserva de cupo. Elige la fecha de nuevo.",
            )
        hold = await self._get_owned(hold_id, user_id=user_id)
        if hold.status != HoldStatus.held:
            raise hold_expired_error(hold_id)
        return hold
