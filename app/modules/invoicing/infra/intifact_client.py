"""Cliente HTTP de Intifact (facturación electrónica SUNAT). Solo lo usa el backend: la key no sale del servidor."""
from __future__ import annotations

from typing import Any, Optional

import httpx

TIMEOUT_SECONDS = 30.0
# Cloudflare (delante de Intifact) rechaza clientes sin un User-Agent de aplicación (error 1010).
USER_AGENT = "paku-backend/1.0"


class IntifactError(Exception):
    def __init__(self, status_code: int, message: str, errors: Optional[list] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.errors = errors or []

    def detail(self) -> str:
        extra = "; ".join(f"{e.get('path')}: {e.get('message')}" for e in self.errors if isinstance(e, dict))
        return self.message + (f" ({extra})" if extra else "")


class IntifactClient:
    def __init__(self, base_url: str, api_key: str, *,
                 transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT, "Accept": "application/json"}
        self._transport = transport  # solo tests

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, timeout=TIMEOUT_SECONDS, headers=self._headers,
                                 transport=self._transport)

    async def _request(self, method: str, path: str, **kw: Any) -> dict:
        try:
            async with self._client() as client:
                r = await client.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise IntifactError(502, "No se pudo conectar con Intifact.") from exc
        try:
            body = r.json()
        except ValueError:
            body = {"message": r.text[:300]}
        if not isinstance(body, dict):
            body = {"data": body}
        if r.status_code >= 400 or body.get("success") is False:
            raise IntifactError(r.status_code if r.status_code >= 400 else 422,
                                body.get("message") or f"Intifact respondió {r.status_code}.", body.get("errors"))
        return body

    async def companies(self) -> list[dict]:
        data = (await self._request("GET", "/companies")).get("data")
        if isinstance(data, dict):
            data = data.get("items") or data.get("companies") or [data]
        return [c for c in (data or []) if isinstance(c, dict)]

    async def compute(self, items: list[dict], *, prices_include_igv: bool = True) -> dict:
        body = {"tipoMoneda": "PEN", "items": items, "preciosIncluyenIgv": prices_include_igv}
        return (await self._request("POST", "/invoice/compute", json=body))["data"]

    async def next_number(self, ruc: str, tipo_doc: str, serie: str) -> int:
        data = (await self._request("GET", "/documents/next-correlativo",
                                    params={"companyRuc": ruc, "tipoDoc": tipo_doc, "serie": serie}))["data"]
        return int((data or {}).get("next") or 1)

    async def send(self, body: dict) -> dict:
        return (await self._request("POST", "/invoice/send", json=body))["data"] or {}

    async def document(self, document_id: str) -> dict:
        return (await self._request("GET", f"/documents/{document_id}"))["data"] or {}

    async def file(self, document_id: str, kind: str, fmt: Optional[str] = None) -> tuple[bytes, str]:
        """PDF, XML firmado o CDR de SUNAT: contenido y tipo."""
        label = {"pdf": "el PDF", "xml": "el XML", "cdr": "el CDR"}[kind]
        try:
            async with self._client() as client:
                r = await client.get(f"/invoice/{document_id}/{kind}", params={"format": fmt} if fmt else None,
                                     headers={"Accept": "*/*"})
        except httpx.HTTPError as exc:
            raise IntifactError(502, f"No se pudo descargar {label} del comprobante.") from exc
        if r.status_code >= 400:
            raise IntifactError(r.status_code, f"No se pudo descargar {label} del comprobante.")
        return r.content, r.headers.get("content-type", "application/octet-stream")

    async def cancel(self, body: dict, *, boleta: bool) -> dict:
        """Factura: comunicación de baja (RA). Boleta: resumen diario con estado anulado (RC)."""
        return (await self._request("POST", "/boleta/cancel" if boleta else "/invoice/cancel", json=body)).get("data") or {}
