"""Adaptadores de la consulta de DNI (feature 0027, PAKU-USERS-007).

La consulta real va contra Datos Perú (``POST {DATOSPERU_URL}/v1/dni/consulta``, su spec 0008) con la clave de API de
cliente de Paku, que solo tiene el servicio ``dni_simple``. Nunca se usa el token de administrador de Datos Perú.
Datos Perú elige el proveedor (Paku no lo elige) y devuelve solo DNI, nombres y apellidos.

Sin ``DATOSPERU_URL`` o sin ``DATOSPERU_API_KEY`` la consulta responde "no disponible" y el usuario escribe sus datos a
mano. La clave nunca se registra en logs ni en errores.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.settings import settings
from app.modules.iam.domain.dni import (
    ConsultaDniLimitada,
    ConsultaDniNoDisponible,
    ConsultorDni,
    DatosDni,
    DniNoEncontrado,
)

logger = logging.getLogger(__name__)

FUENTE_DATOSPERU = "datosperu"
_NO_DISPONIBLE = "La consulta de DNI no está disponible por ahora."
# Retry-After de Datos Perú: si falta o no es un entero, se usa 60 s; se acota a un día.
_ESPERA_POR_DEFECTO = 60
_ESPERA_MAXIMA = 86400


def _segundos_de_espera(valor: Optional[str]) -> int:
    try:
        segundos = int((valor or "").strip())
    except ValueError:
        return _ESPERA_POR_DEFECTO
    return min(max(segundos, 1), _ESPERA_MAXIMA)


class ConsultorDniNoDisponible:
    """Adaptador por defecto: no hay proveedor configurado."""

    async def consultar(self, dni: str) -> DatosDni:
        raise ConsultaDniNoDisponible(_NO_DISPONIBLE)


class ConsultorDniDatosPeru:
    """Consulta de DNI en Datos Perú con la clave de cliente de Paku.

    - 200 → nombres y apellidos (fuente ``datosperu``).
    - 404 → DniNoEncontrado.
    - 429 (límite de Datos Perú) → ConsultaDniLimitada con su ``Retry-After`` (60 s si falta).
    - 401/403 (clave inválida o sin ``dni_simple``), 422, 5xx, timeout, error de red o respuesta con forma inesperada
      → ConsultaDniNoDisponible. El detalle va al log sin la clave ni el DNI.
    - Un solo intento: sin reintentos (cada intento puede consumir una consulta del proveedor).
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        timeout: float = 5.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._url = url.rstrip("/") + "/v1/dni/consulta"
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport  # pruebas: httpx.MockTransport

    async def consultar(self, dni: str) -> DatosDni:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as cliente:
                respuesta = await cliente.post(
                    self._url,
                    json={"dni": dni},
                    headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
                )
        except httpx.HTTPError as error:
            logger.warning("Consulta de DNI a Datos Perú sin respuesta: %s", type(error).__name__)
            raise ConsultaDniNoDisponible(_NO_DISPONIBLE) from None

        if respuesta.status_code == 404:
            raise DniNoEncontrado("DNI no encontrado.")
        if respuesta.status_code == 429:
            espera = _segundos_de_espera(respuesta.headers.get("Retry-After"))
            logger.warning("Consulta de DNI a Datos Perú limitada; reintentar en %s s", espera)
            raise ConsultaDniLimitada(espera)
        if respuesta.status_code != 200:
            logger.warning("Consulta de DNI a Datos Perú respondió %s", respuesta.status_code)
            raise ConsultaDniNoDisponible(_NO_DISPONIBLE)
        try:
            cuerpo = respuesta.json()
            nombres = str(cuerpo["nombres"]).strip()
            apellidos = str(cuerpo["apellidos"]).strip()
        except (ValueError, KeyError, TypeError):
            logger.warning("Consulta de DNI a Datos Perú con respuesta de forma inesperada")
            raise ConsultaDniNoDisponible(_NO_DISPONIBLE) from None
        if not nombres or not apellidos:
            logger.warning("Consulta de DNI a Datos Perú sin nombres o apellidos")
            raise ConsultaDniNoDisponible(_NO_DISPONIBLE)
        return DatosDni(nombres=nombres, apellidos=apellidos, fuente=FUENTE_DATOSPERU)


def obtener_consultor_dni() -> ConsultorDni:
    """Dependencia de FastAPI: Datos Perú si está configurado; si no, "no disponible"."""
    if settings.DATOSPERU_URL and settings.DATOSPERU_API_KEY:
        return ConsultorDniDatosPeru(
            url=settings.DATOSPERU_URL,
            api_key=settings.DATOSPERU_API_KEY,
            timeout=settings.DATOSPERU_TIMEOUT_SEGUNDOS,
        )
    return ConsultorDniNoDisponible()
