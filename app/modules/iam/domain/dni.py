"""DNI peruano: formato y consulta (feature 0027, bloque B de la integración Paku–HCVet)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Protocol

# [0-9] y no \d: \d acepta dígitos Unicode no latinos.
_PATRON_DNI = re.compile(r"^[0-9]{8}$")


def normalizar_dni(valor: Optional[str]) -> Optional[str]:
    """DNI de 8 dígitos sin espacios. Vacío o solo espacios cuenta como no enviado (None).

    Lanza ValueError si no tiene el formato: Pydantic lo convierte en 422.
    """
    if valor is None:
        return None
    limpio = str(valor).strip()
    if not limpio:
        return None
    if not _PATRON_DNI.match(limpio):
        raise ValueError("El DNI debe tener 8 dígitos.")
    return limpio


# --- Consulta de DNI (puerto) ---


@dataclass(frozen=True)
class DatosDni:
    """Lo único que la consulta devuelve: nombres y apellidos para autocompletar. No prueba titularidad."""

    nombres: str
    apellidos: str
    # Quién entregó los datos (p. ej. "datosperu"). Se guarda como procedencia de los nombres legales.
    fuente: str = "desconocida"


class DniNoEncontrado(Exception):
    """El proveedor no tiene ese DNI."""


class ConsultaDniNoDisponible(Exception):
    """El servicio de consulta no está disponible: sin configurar, caído, timeout o error del proveedor."""


class ConsultaDniLimitada(Exception):
    """El proveedor (Datos Perú) rechazó la consulta por su límite. ``reintentar_en``: segundos (su Retry-After)."""

    def __init__(self, reintentar_en: int) -> None:
        super().__init__(f"La consulta de DNI está ocupada. Reintenta en {reintentar_en} segundos.")
        self.reintentar_en = reintentar_en


class ConsultorDni(Protocol):
    async def consultar(self, dni: str) -> DatosDni:
        """Nombres y apellidos del DNI. Lanza DniNoEncontrado o ConsultaDniNoDisponible."""
        ...
