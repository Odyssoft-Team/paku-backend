"""Cada cuánto puede el dueño cambiar el peso de su mascota (feature 0006).

El peso define el tramo de precio. El dueño lo puede cambiar una vez cada
`PET_WEIGHT_CHANGE_COOLDOWN_DAYS` días (30 por defecto); el groomer y el admin, siempre. Con un
servicio solicitado el dueño tampoco puede (feature 0003, `PET_WEIGHT_LOCKED`).

El peso que se pone al registrar la mascota no cuenta: el primer cambio es libre (corregir un error).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.settings import settings


def weight_editable_from(weight_updated_at: Optional[datetime], now: Optional[datetime] = None) -> Optional[datetime]:
    """Desde cuándo el dueño puede volver a cambiar el peso; None si ya puede."""
    if weight_updated_at is None:
        return None
    if weight_updated_at.tzinfo is None:
        weight_updated_at = weight_updated_at.replace(tzinfo=timezone.utc)
    until = weight_updated_at + timedelta(days=settings.PET_WEIGHT_CHANGE_COOLDOWN_DAYS)
    return until if until > (now or datetime.now(timezone.utc)) else None
