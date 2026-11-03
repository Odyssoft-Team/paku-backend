"""Facturación electrónica con Nubefact (feature 0020): reglas de la configuración y lo que dice su manual.

Manual JSON de Nubefact (facturas, boletas y notas): una RUTA única por cuenta + TOKEN, todo por POST a la RUTA con
`Authorization: <token>` y `Content-Type: application/json`. Operaciones: `generar_comprobante`,
`consultar_comprobante`, `generar_anulacion`, `consultar_anulacion`. Esta fase solo guarda la configuración y prueba
la conexión; todavía no se emite ningún comprobante.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

PROVIDER = "nubefact"

# tipo_de_comprobante del manual
TIPO_FACTURA, TIPO_BOLETA, TIPO_NOTA_CREDITO, TIPO_NOTA_DEBITO = 1, 2, 3, 4

# Serie de boletas: 4 caracteres que empiezan con «B» (las de contingencia empiezan con «0»; no se usan aquí)
BOLETA_SERIES_RE = re.compile(r"^B[A-Z0-9]{3}$")
DEFAULT_BOLETA_SERIES = "B001"

# Códigos de error del manual (campo `codigo` de la respuesta)
ERROR_CODES: dict[int, str] = {
    10: "El token es incorrecto o fue eliminado.",
    11: "La ruta (URL) es incorrecta o no existe.",
    12: "Encabezado Content-Type incorrecto.",
    20: "El documento no tiene el formato esperado.",
    21: "No se pudo completar la operación.",
    22: "Documento enviado fuera del plazo permitido.",
    23: "El documento ya existe.",
    24: "El documento no existe o no fue enviado.",
    40: "Error interno desconocido de Nubefact.",
    50: "La cuenta de Nubefact está suspendida.",
    51: "La cuenta de Nubefact está suspendida por falta de pago.",
}
DOCUMENT_NOT_FOUND = 24

# Número que no se va a emitir nunca: la prueba de conexión lo consulta (no emite nada)
PROBE_NUMBER = 99999999


class InvoicingConfigInvalid(Exception):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def normalize_route(value: str) -> str:
    """RUTA de la cuenta: https (o http solo para la versión offline en localhost)."""
    route = value.strip().rstrip("/")
    parsed = urlparse(route)
    local = parsed.hostname in ("localhost", "127.0.0.1")
    if parsed.scheme not in ("https", "http") or not parsed.hostname or (parsed.scheme == "http" and not local):
        raise InvoicingConfigInvalid("api_url", "La ruta debe ser una URL https, p. ej. https://api.nubefact.com/api/v1/…")
    if not parsed.path or parsed.path == "/":
        raise InvoicingConfigInvalid("api_url", "Falta la parte final de la ruta (el identificador de tu cuenta).")
    return route


def normalize_series(value: str) -> str:
    series = value.strip().upper()
    if not BOLETA_SERIES_RE.match(series):
        raise InvoicingConfigInvalid("boleta_series", "La serie de boletas tiene 4 caracteres y empieza con B (p. ej. B001).")
    return series


def check_token(value: str) -> str:
    token = value.strip()
    if not token or any(c.isspace() for c in token):
        raise InvoicingConfigInvalid("token", "El token no puede estar vacío ni tener espacios.")
    return token


def error_message(codigo: Optional[int], errors: Optional[str]) -> str:
    known = ERROR_CODES.get(codigo) if codigo is not None else None
    parts = [p for p in (known, errors) if p]
    return " ".join(dict.fromkeys(parts)) or "Nubefact respondió con un error."
