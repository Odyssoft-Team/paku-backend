"""
Cupo de una orden cuando el admin la asigna a un día (C-21, regla de negocio 2026-10-05).

Reprogramar lo pide el cliente y lo acepta el admin: el admin puede cambiar el día sin que el cliente
compre de nuevo. Al asignar:
  - mismo día de la reserva vigente  → no cambia el cupo (solo la hora);
  - otro día                         → se toma cupo del día nuevo y se libera el del día original;
  - sin reserva vigente (p. ej. venía de skipped y se liberó) → se toma cupo del día elegido.
Si el día elegido no tiene cupo → 409 NO_CAPACITY con un mensaje legible (el admin lo muestra tal cual).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.booking.domain.hold import Hold, HoldStatus
from app.modules.cart.domain.cart import CART_TTL_HOURS


def no_capacity_error(day: date) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "NO_CAPACITY",
            "message": f"No hay cupos disponibles para el {day.strftime('%d/%m/%Y')}. Elige otro día o amplía la capacidad.",
            "date": day.isoformat(),
        },
    )


async def reserve_day_for_order(
    *, holds_repo, availability_repo, user_id: UUID, pet_id: UUID, service_id: UUID, day: date,
) -> Hold:
    """Toma un cupo del día para la orden y lo deja confirmado (no vence)."""
    slot = await availability_repo.get_slot_for_update(service_id, day)
    if slot is None or not slot.is_active or not slot.has_capacity:
        raise no_capacity_error(day)
    await availability_repo.increment_booked(slot.id)
    hold = await holds_repo.create_hold(
        user_id=user_id,
        pet_id=pet_id,
        service_id=service_id,
        # Vence lejos solo para que no expire antes de confirmarla en la línea siguiente.
        expires_at=datetime.now(timezone.utc) + timedelta(hours=CART_TTL_HOURS),
        date=day,
    )
    confirmed = await holds_repo.update_status(hold.id, HoldStatus.confirmed)
    return confirmed or hold
