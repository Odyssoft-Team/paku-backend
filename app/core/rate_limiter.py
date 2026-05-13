"""
Rate limiter en memoria para proteger endpoints sensibles (login, forgot-password).

Diseño deliberadamente simple: no requiere Redis.
- Funciona bien con una sola instancia (Cloud Run con min-instances=1).
- Si hay múltiples instancias, cada una tiene su propio contador — aceptable
  porque el objetivo es dificultar ataques, no garantía absoluta.
- TTL automático: las entradas se limpian cuando expiran, sin background task.

Uso:
    from app.core.rate_limiter import login_limiter
    login_limiter.check(key="192.168.1.1")   # lanza 429 si excede el límite
    login_limiter.record_failure(key="192.168.1.1")
    login_limiter.record_success(key="192.168.1.1")  # resetea el contador
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict

from fastapi import HTTPException, status


@dataclass
class _Entry:
    failures: int = 0
    window_start: float = field(default_factory=time.monotonic)


class RateLimiter:
    """
    Limita intentos fallidos por clave (normalmente IP) dentro de una ventana de tiempo.

    Args:
        max_failures: Número máximo de fallos permitidos en la ventana.
        window_seconds: Duración de la ventana en segundos.
        lockout_seconds: Tiempo de bloqueo tras superar el límite (puede diferir de la ventana).
    """

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 900,   # 15 minutos
        lockout_seconds: int = 900,
    ) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._lockout = lockout_seconds
        self._store: Dict[str, _Entry] = {}
        self._lock = Lock()

    def _now(self) -> float:
        return time.monotonic()

    def _get_or_create(self, key: str) -> _Entry:
        entry = self._store.get(key)
        if entry is None or (self._now() - entry.window_start) > self._window:
            entry = _Entry(window_start=self._now())
            self._store[key] = entry
        return entry

    def check(self, key: str) -> None:
        """Lanza HTTP 429 si la clave está bloqueada."""
        with self._lock:
            entry = self._get_or_create(key)
            elapsed = self._now() - entry.window_start
            if entry.failures >= self._max and elapsed < self._lockout:
                retry_after = int(self._lockout - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "TOO_MANY_ATTEMPTS",
                        "message": "Demasiados intentos fallidos. Intenta de nuevo más tarde.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

    def record_failure(self, key: str) -> None:
        """Incrementa el contador de fallos para la clave."""
        with self._lock:
            entry = self._get_or_create(key)
            entry.failures += 1

    def record_success(self, key: str) -> None:
        """Resetea el contador al autenticar correctamente."""
        with self._lock:
            self._store.pop(key, None)

    def _cleanup(self) -> None:
        """Elimina entradas expiradas (llamar periódicamente si se desea)."""
        now = self._now()
        with self._lock:
            expired = [k for k, v in self._store.items() if (now - v.window_start) > self._lockout]
            for k in expired:
                del self._store[k]


# Instancias globales — una por endpoint sensible
login_limiter = RateLimiter(max_failures=5, window_seconds=900, lockout_seconds=900)
forgot_password_limiter = RateLimiter(max_failures=3, window_seconds=3600, lockout_seconds=3600)
