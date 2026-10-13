from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional

import httpx

from app.core.settings import settings

logger = logging.getLogger(__name__)

# Respuestas de culqi-python que prueban que el cargo no llegó a Culqi: su propia validación (422),
# Idempotency-Key ausente (400), API key inválida (401/403) o ruta inexistente (404).
_NOT_CHARGED_STATUS_CODES = frozenset({400, 401, 403, 404, 422})


class CulqiChargeRejected(Exception):
    """Culqi respondió y rechazó el cargo de forma definitiva."""

    def __init__(self, detail: Any) -> None:
        self.detail = detail
        super().__init__(str(detail))


class CulqiResultAmbiguous(Exception):
    """No se pudo determinar si Culqi completó el cargo."""


class CulqiChargeNotAttempted(Exception):
    """culqi-python rechazó la petición antes de llamar a Culqi: no hubo cargo."""

    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


class CulqiAuthenticationRequired(Exception):
    """Culqi respondió 200 sin cargo: la tarjeta necesita autenticación 3D Secure."""

    def __init__(self, detail: Any) -> None:
        self.detail = detail
        super().__init__(str(detail))


class CulqiOperationFailed(Exception):
    """El servicio de pagos devolvió un rechazo explícito para Customer o Card."""


class CulqiOperationAmbiguous(CulqiOperationFailed):
    """No se pudo determinar si Culqi creó el Customer o la Card."""


def _summary(result: Any) -> Any:
    """Campos de diagnóstico de una respuesta 200 sin cargo (sin datos de la tarjeta)."""
    if not isinstance(result, dict):
        return type(result).__name__
    keys = ("object", "action_code", "user_message", "merchant_message", "culqi_tracking_id")
    return {k: result.get(k) for k in keys if k in result}


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
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.warning("culqi-python charge order=%s sin respuesta: %r", order_id, exc)
            raise CulqiResultAmbiguous()

        try:
            result = response.json()
        except ValueError as exc:
            logger.warning("culqi-python charge order=%s status=%s respuesta no JSON", order_id, response.status_code)
            raise CulqiResultAmbiguous() from exc

        if response.status_code == 200:
            if isinstance(result, dict) and result.get("id"):
                return result
            # Culqi responde 200 (no 201) sin cargo cuando la tarjeta exige 3D Secure
            # (action_code=REVIEW); culqi-python lo reenvía tal cual.
            logger.warning("culqi-python charge order=%s 200 sin id: %s", order_id, _summary(result))
            if isinstance(result, dict) and result.get("action_code") == "REVIEW":
                raise CulqiAuthenticationRequired(result)
            raise CulqiResultAmbiguous()

        detail = result.get("detail") if isinstance(result, dict) else None
        logger.warning("culqi-python charge order=%s status=%s detail=%s", order_id, response.status_code, detail)
        if isinstance(detail, dict) and detail.get("outcome") == "rejected":
            raise CulqiChargeRejected(detail)
        if response.status_code in _NOT_CHARGED_STATUS_CODES:
            raise CulqiChargeNotAttempted(response.status_code, detail)
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