"""Cliente de HCVet desde Paku Backend (feature 0028, REQUIREMENTS §5).

- Se autentica con la API Key de Paku (``Authorization: Bearer hcv_…``), configurada solo en el backend
  (``HCVET_URL`` con ``/v1`` y ``HCVET_API_KEY``). La clave nunca va a logs, errores ni respuestas.
- Reutiliza los contratos de HCVet (feature 0005 de HCVet, ``docs/INTEGRACION.md``): alta con ``Idempotency-Key``,
  autorizaciones (vinculación de acceso básico, D-105), consentimientos por finalidad y actualización con ``datos_al``.
- Clasifica cada falla para decidir si se reintenta:
    - ``temporal``: timeout, error de red, 5xx o 429 (con ``Retry-After``). Se reintenta.
    - ``conflicto``: 409. No se reintenta.
    - ``no_encontrado``: 404 (no existe o Paku ya no tiene autorización: HCVet no distingue). No se reintenta.
    - ``permanente``: 400, 401, 403, 422 u otra respuesta inesperada. No se reintenta.
- Los detalles de error se guardan sin DNI, teléfonos ni correos.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.core.settings import settings
from app.modules.hcvet.domain.sincronizacion import sin_datos_personales

logger = logging.getLogger(__name__)

TEMPORAL = "temporal"
CONFLICTO = "conflicto"
NO_ENCONTRADO = "no_encontrado"
PERMANENTE = "permanente"

_ESPERA_POR_DEFECTO = 60
_ESPERA_MAXIMA = 86400


class HcvetNoConfigurado(Exception):
    """Falta HCVET_URL o HCVET_API_KEY: no se intenta nada."""


class ErrorHcvet(Exception):
    def __init__(self, tipo: str, mensaje: str, *, status: Optional[int] = None, retry_after: Optional[int] = None):
        super().__init__(mensaje)
        self.tipo = tipo
        self.status = status
        self.mensaje = mensaje
        self.retry_after = retry_after

    @property
    def reintentable(self) -> bool:
        return self.tipo == TEMPORAL


def _retry_after(valor: Optional[str]) -> int:
    try:
        segundos = int((valor or "").strip())
    except ValueError:
        return _ESPERA_POR_DEFECTO
    return min(max(segundos, 1), _ESPERA_MAXIMA)


def _detalle(respuesta: httpx.Response) -> str:
    try:
        detalle = respuesta.json().get("detail")
    except Exception:
        return ""
    if isinstance(detalle, list):  # 422 de HCVet: solo ubicaciones y mensajes, sin valores
        return "; ".join(f"{'.'.join(str(p) for p in d.get('loc', []))}: {d.get('msg', '')}" for d in detalle[:5])
    return str(detalle or "")


def clasificar(respuesta: httpx.Response) -> ErrorHcvet:
    status = respuesta.status_code
    detalle = sin_datos_personales(_detalle(respuesta))
    if status == 429:
        return ErrorHcvet(TEMPORAL, "HCVet limitó las peticiones.", status=status,
                          retry_after=_retry_after(respuesta.headers.get("Retry-After")))
    if status >= 500:
        return ErrorHcvet(TEMPORAL, f"HCVet respondió {status}.", status=status)
    if status == 409:
        return ErrorHcvet(CONFLICTO, detalle or "HCVet rechazó el cambio por un conflicto.", status=status)
    if status == 404:
        return ErrorHcvet(NO_ENCONTRADO, "HCVet no encontró el propietario o Paku no tiene autorización vigente.",
                          status=status)
    if status == 401:
        return ErrorHcvet(PERMANENTE, "HCVet rechazó la API Key de Paku (inválida, revocada o vencida).", status=status)
    if status == 403:
        return ErrorHcvet(PERMANENTE, detalle or "La autorización de Paku no incluye ese alcance.", status=status)
    if status == 422:
        return ErrorHcvet(PERMANENTE, f"HCVet rechazó los datos: {detalle}"[:300], status=status)
    return ErrorHcvet(PERMANENTE, f"Respuesta inesperada de HCVet ({status}).", status=status)


@dataclass(frozen=True)
class ConfiguracionHcvet:
    url: str
    api_key: str
    timeout: float = 10.0

    @property
    def completa(self) -> bool:
        return bool(self.url and self.api_key)

    @classmethod
    def desde_settings(cls) -> "ConfiguracionHcvet":
        return cls(settings.HCVET_URL, settings.HCVET_API_KEY, settings.HCVET_TIMEOUT_SEGUNDOS)


class ClienteHcvet:
    """Operaciones de HCVet que usa la integración de propietarios. Cada método hace un solo intento: los reintentos
    los decide el procesador de operaciones."""

    def __init__(self, config: ConfiguracionHcvet, *, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.config = config
        self._transport = transport

    @property
    def configurado(self) -> bool:
        return self.config.completa

    async def _pedir(self, metodo: str, ruta: str, *, json: Any = None,
                     cabeceras: Optional[dict[str, str]] = None) -> httpx.Response:
        if not self.configurado:
            raise HcvetNoConfigurado("HCVet no está configurado.")
        headers = {"Authorization": f"Bearer {self.config.api_key}", **(cabeceras or {})}
        try:
            async with httpx.AsyncClient(base_url=self.config.url, timeout=self.config.timeout,
                                         transport=self._transport) as http:
                respuesta = await http.request(metodo, ruta, json=json, headers=headers)
        except httpx.TimeoutException as exc:
            raise ErrorHcvet(TEMPORAL, "HCVet no respondió a tiempo.") from exc
        except httpx.HTTPError as exc:
            logger.warning("HCVet no disponible: %s", exc.__class__.__name__)
            raise ErrorHcvet(TEMPORAL, "No se pudo conectar con HCVet.") from exc
        if respuesta.status_code >= 400:
            error = clasificar(respuesta)
            logger.info("HCVet %s %s → %s", metodo, ruta.split("/")[1] if "/" in ruta else ruta, respuesta.status_code)
            raise error
        return respuesta

    @staticmethod
    def _json(respuesta: httpx.Response) -> Any:
        try:
            return respuesta.json()
        except ValueError as exc:
            raise ErrorHcvet(TEMPORAL, "HCVet devolvió una respuesta que no es JSON.") from exc

    async def registrar_propietario(self, cuerpo: dict, *, clave_idempotencia: str) -> dict:
        """POST /propietarios. 201 nuevo o 200 ya registrado por Paku; 409 si el DNI ya existe en HCVet."""
        respuesta = await self._pedir("POST", "/propietarios", json=cuerpo,
                                      cabeceras={"Idempotency-Key": clave_idempotencia})
        datos = self._json(respuesta)
        if not isinstance(datos, dict) or "propietario_id" not in datos or "autorizacion_id" not in datos:
            raise ErrorHcvet(PERMANENTE, "HCVet devolvió un alta sin identificadores.")
        return datos

    async def otorgar_autorizacion(self, dni: str, cuerpo: dict) -> dict:
        """POST /propietarios/{dni}/autorizaciones: vincularse a un propietario existente (acceso básico, HCVet D-105)."""
        datos = self._json(await self._pedir("POST", f"/propietarios/{dni}/autorizaciones", json=cuerpo))
        if not isinstance(datos, dict) or "id" not in datos:
            raise ErrorHcvet(PERMANENTE, "HCVet devolvió una autorización sin identificador.")
        return datos

    async def listar_autorizaciones(self, dni: str) -> list[dict]:
        """GET /propietarios/{dni}/autorizaciones: las de Paku (para recuperar una creada antes de un timeout)."""
        datos = self._json(await self._pedir("GET", f"/propietarios/{dni}/autorizaciones"))
        return datos if isinstance(datos, list) else []

    async def revocar_autorizacion(self, dni: str, autorizacion_id: int) -> None:
        await self._pedir("DELETE", f"/propietarios/{dni}/autorizaciones/{autorizacion_id}")

    async def registrar_consentimiento(self, dni: str, tipo: str, cuerpo: dict) -> dict:
        return self._json(await self._pedir("PUT", f"/propietarios/{dni}/consentimientos/{tipo}", json=cuerpo))

    async def actualizar_propietario(self, dni: str, cuerpo: dict) -> dict:
        return self._json(await self._pedir("PATCH", f"/propietarios/{dni}", json=cuerpo))


def cliente_desde_settings() -> ClienteHcvet:
    return ClienteHcvet(ConfiguracionHcvet.desde_settings())
