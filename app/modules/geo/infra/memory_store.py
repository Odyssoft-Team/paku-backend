"""Cache con vencimiento y contadores de uso en memoria (feature 0002).

Mismo criterio que `app/core/rate_limiter.py`: sin Redis. El backend corre en
una sola instancia; con varias, cada una tendría sus propios contadores, lo
que sigue limitando el gasto (solo que con un tope por instancia).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Callable, Hashable, Optional


class TTLCache:
    """Cache clave → valor con vencimiento y tamaño máximo (descarta el más antiguo)."""

    def __init__(self, *, ttl_seconds: float, max_items: int = 5000, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._max = max_items
        self._clock = clock
        self._data: "OrderedDict[Hashable, tuple[float, Any]]" = OrderedDict()
        self._lock = Lock()

    def get(self, key: Hashable) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if self._clock() >= expires_at:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._data[key] = (self._clock() + self._ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)


class UsageLimiter:
    """Cuenta usos por clave en una ventana fija; `hit` devuelve False si se pasó del límite."""

    def __init__(self, *, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._data: dict[Hashable, tuple[float, int]] = {}
        self._lock = Lock()

    def hit(self, key: Hashable) -> bool:
        now = self._clock()
        with self._lock:
            start, count = self._data.get(key, (now, 0))
            if now - start >= self._window:
                start, count = now, 0
            if count >= self._limit:
                self._data[key] = (start, count)
                return False
            self._data[key] = (start, count + 1)
            # Limpieza perezosa para que el diccionario no crezca sin fin
            if len(self._data) > 10000:
                self._data = {k: v for k, v in self._data.items() if now - v[0] < self._window}
            return True
