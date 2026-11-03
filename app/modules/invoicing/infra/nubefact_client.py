"""Cliente HTTP de Nubefact (manual JSON): POST a la RUTA con `Authorization: <token>` (sin «Bearer»)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.modules.invoicing.domain.nubefact import TIPO_BOLETA

TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class NubefactResponse:
    status_code: int
    data: dict
    codigo: Optional[int]          # código de error del manual (10, 11, 24…) si lo hay
    errors: Optional[str]


class NubefactUnreachable(Exception):
    pass


class NubefactClient:
    def __init__(self, api_url: str, token: str, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._url = api_url
        self._token = token
        self._transport = transport  # solo tests

    async def post(self, body: dict) -> NubefactResponse:
        headers = {"Authorization": self._token, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.post(self._url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise NubefactUnreachable(f"No se pudo conectar con Nubefact: {exc.__class__.__name__}.") from exc
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        codigo = data.get("codigo")
        try:
            codigo = int(codigo) if codigo is not None else None
        except (TypeError, ValueError):
            codigo = None
        errors = data.get("errors")
        return NubefactResponse(response.status_code, data, codigo, str(errors) if errors else None)

    async def consultar_boleta(self, *, serie: str, numero: int) -> NubefactResponse:
        return await self.post({"operacion": "consultar_comprobante", "tipo_de_comprobante": TIPO_BOLETA,
                                "serie": serie, "numero": numero})
