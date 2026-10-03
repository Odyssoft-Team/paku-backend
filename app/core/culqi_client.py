from __future__ import annotations

import hashlib
from typing import Any, Optional

import httpx

from app.core.settings import settings


class CulqiChargeRejected(Exception):
    """Culqi respondió y rechazó el cargo de forma definitiva."""

    def __init__(self, detail: Any) -> None:
        self.detail = detail
        super().__init__(str(detail))


class CulqiResultAmbiguous(Exception):
    """No se pudo determinar si Culqi completó el cargo."""


class CulqiOperationFailed(Exception):
    """El servicio de pagos devolvió un rechazo explícito para Customer o Card."""


class CulqiOperationAmbiguous(CulqiOperationFailed):
    """No se pudo determinar si Culqi creó el Customer o la Card."""


class CulqiPythonClient:
    """Cliente servidor-a-servidor del adaptador culqi-python."""

    def __init__(self) -> None:
        self._base_url = settings.CULQI_PYTHON_BASE_URL
        self._api_key = settings.CULQI_PYTHON_SERVICE_API_KEY

    def _headers(self, *, idempotency_key: Optional[str] = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def _create_resource(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
                response = await client.post(path, json=payload, headers=self._headers())
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise CulqiOperationAmbiguous() from exc

        if response.status_code == 502:
            try:
                detail = response.json().get("detail")
                provider_status_code = detail.get("provider_status_code")
            except (AttributeError, ValueError):
                raise CulqiOperationAmbiguous()
            if not isinstance(provider_status_code, int) or provider_status_code >= 500:
                raise CulqiOperationAmbiguous()
            raise CulqiOperationFailed()
        if response.status_code >= 500:
            raise CulqiOperationAmbiguous()
        if response.status_code != 200:
            raise CulqiOperationFailed()
        try:
            result = response.json()
        except ValueError as exc:
            raise CulqiOperationAmbiguous() from exc
        if not isinstance(result, dict):
            raise CulqiOperationAmbiguous()
        return result

    async def create_customer(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        country_code: str,
        address: str,
        address_city: str,
        phone_number: str,
    ) -> dict[str, Any]:
        return await self._create_resource(
            "/api/culqi/customers",
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "country_code": country_code,
                "address": address,
                "address_city": address_city,
                "phone_number": phone_number,
            },
        )

    async def create_card(self, *, customer_id: str, token_id: str) -> dict[str, Any]:
        return await self._create_resource(
            "/api/culqi/cards",
            {"customer_id": customer_id, "token_id": token_id},
        )

    async def create_charge(
        self,
        *,
        order_id: str,
        amount: int,
        currency_code: str,
        email: str,
        source_id: str,
        metadata: Optional[dict[str, str]] = None,
        antifraud_details: Optional[dict[str, str]] = None,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "amount": amount,
            "currency_code": currency_code,
            "email": email,
            "source_id": source_id,
            "order_id": order_id,
            "metadata": metadata or {},
        }
        if antifraud_details:
            payload["antifraud_details"] = antifraud_details
        # Una clave por (orden, medio de pago): reintentar con el mismo token repite el mismo intento
        # (culqi-python devuelve el resultado cacheado, sin doble cobro); pagar con otra tarjeta tras un
        # rechazo es un intento nuevo. Con una clave fija por orden, culqi-python respondía 409 y la
        # orden quedaba trabada en "verifying".
        source_hash = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:16]
        idempotency_key = f"order-{order_id}-payment-{source_hash}"

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
                response = await client.post(
                    "/api/culqi/charges",
                    json=payload,
                    headers=self._headers(idempotency_key=idempotency_key),
                )
        except (httpx.TimeoutException, httpx.TransportError):
            raise CulqiResultAmbiguous()

        try:
            result = response.json()
        except ValueError as exc:
            raise CulqiResultAmbiguous() from exc

        if response.status_code == 200:
            if isinstance(result, dict) and result.get("id"):
                return result
            raise CulqiResultAmbiguous()

        detail = result.get("detail") if isinstance(result, dict) else None
        if isinstance(detail, dict) and detail.get("outcome") == "rejected":
            raise CulqiChargeRejected(detail)
        raise CulqiResultAmbiguous()

    async def find_payments(self, *, order_id: str, timeout: float = 10.0) -> Optional[list[dict[str, Any]]]:
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
                response = await client.get(
                    "/api/culqi/payments",
                    params={"order_id": order_id},
                    headers=self._headers(),
                )
        except (httpx.TimeoutException, httpx.TransportError):
            return None

        if response.status_code != 200:
            return None
        return response.json()