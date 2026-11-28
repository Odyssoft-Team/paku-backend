"""Consulta de DNI para autocompletar nombres y apellidos (feature 0027).

Protecciones (REQUIREMENTS §4.3): solo el propio usuario con sesión, límites por usuario (consultas por hora y DNI
distintos por día) y caché para no consumir el proveedor con consultas repetidas. No es un buscador de personas.
Límites y caché viven en memoria del proceso (como ``app/core/rate_limiter.py``).
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from app.modules.iam.domain.dni import ConsultorDni, DatosDni

HORA = 3600.0
DIA = 86400.0


class LimiteConsultaDni(Exception):
    """Se superó un límite. ``reintentar_en``: segundos para volver a intentar."""

    def __init__(self, reintentar_en: int) -> None:
        super().__init__(f"Demasiadas consultas de DNI. Reintente en {reintentar_en} segundos.")
        self.reintentar_en = reintentar_en


@dataclass
class LimitesConsultaDni:
    """Por usuario: consultas por hora y DNI distintos por día. Seguro entre hilos."""

    por_hora: int
    distintos_por_dia: int
    reloj: Callable[[], float] = time.monotonic
    _consultas: dict[UUID, deque[float]] = field(default_factory=dict)
    _distintos: dict[UUID, dict[str, float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def registrar(self, usuario: UUID, dni: str) -> None:
        """Cuenta la consulta o lanza LimiteConsultaDni. Una consulta rechazada no cuenta."""
        with self._lock:
            ahora = self.reloj()
            consultas = self._consultas.setdefault(usuario, deque())
            while consultas and consultas[0] <= ahora - HORA:
                consultas.popleft()
            distintos = self._distintos.setdefault(usuario, {})
            for valor, momento in list(distintos.items()):
                if momento <= ahora - DIA:
                    del distintos[valor]
            esperas = []
            if len(consultas) >= self.por_hora:
                esperas.append(consultas[0] + HORA - ahora)
            if dni not in distintos and len(distintos) >= self.distintos_por_dia:
                esperas.append(min(distintos.values()) + DIA - ahora)
            if esperas:
                raise LimiteConsultaDni(max(1, math.ceil(max(esperas))))
            consultas.append(ahora)
            distintos.setdefault(dni, ahora)

    def reiniciar(self) -> None:
        with self._lock:
            self._consultas.clear()
            self._distintos.clear()


@dataclass
class CacheDni:
    """Resultados exitosos por DNI durante ``duracion`` segundos."""

    duracion: float
    reloj: Callable[[], float] = time.monotonic
    _datos: dict[str, tuple[float, DatosDni]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def obtener(self, dni: str) -> DatosDni | None:
        with self._lock:
            entrada = self._datos.get(dni)
            if entrada is None or entrada[0] <= self.reloj():
                self._datos.pop(dni, None)
                return None
            return entrada[1]

    def guardar(self, dni: str, datos: DatosDni) -> None:
        with self._lock:
            self._datos[dni] = (self.reloj() + self.duracion, datos)

    def reiniciar(self) -> None:
        with self._lock:
            self._datos.clear()


@dataclass
class ConsultarDni:
    consultor: ConsultorDni
    limites: LimitesConsultaDni
    cache: CacheDni

    async def execute(self, usuario: UUID, dni: str) -> DatosDni:
        """``dni`` ya normalizado. Los límites cuentan también las consultas que salen de la caché."""
        self.limites.registrar(usuario, dni)
        guardado = self.cache.obtener(dni)
        if guardado is not None:
            return guardado
        datos = await self.consultor.consultar(dni)
        self.cache.guardar(dni, datos)
        return datos
