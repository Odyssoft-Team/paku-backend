"""Registro de envíos (feature 0018 fase 2): estados y reintentos.

- `PENDING`: registrado, aún sin respuesta del proveedor. `SENT`: el proveedor lo aceptó. `FAILED`: rechazado o sin
  configuración.
- Solo se reintentan solas las fallas temporales (límite de envíos, caída, sin conexión), hasta `MAX_ATTEMPTS`
  intentos, esperando `RETRY_DELAYS_MINUTES` entre uno y otro. El admin puede reintentar a mano cualquier `FAILED`.
- Un `PENDING` que quedó colgado más de `STUCK_PENDING_MINUTES` (p. ej. el servidor se reinició a mitad del envío)
  se vuelve a intentar con la misma `idempotency_key`, así el proveedor no lo duplica.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

PENDING, SENT, FAILED = "PENDING", "SENT", "FAILED"
STATUSES = (PENDING, SENT, FAILED)

MAX_ATTEMPTS = 5
RETRY_DELAYS_MINUTES = (1, 5, 15, 60)
STUCK_PENDING_MINUTES = 10


def next_attempt_at(attempts: int, *, now: datetime) -> Optional[datetime]:
    """Cuándo reintentar tras `attempts` intentos fallidos; None si ya no quedan."""
    if attempts >= MAX_ATTEMPTS:
        return None
    delay = RETRY_DELAYS_MINUTES[min(max(attempts, 1), len(RETRY_DELAYS_MINUTES)) - 1]
    return now + timedelta(minutes=delay)
