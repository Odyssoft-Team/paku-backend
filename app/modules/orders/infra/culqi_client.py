from __future__ import annotations

from typing import Any, Optional

import httpx

from app.core.settings import settings


class CulqiChargeRejected(Exception):
    """Culqi respondió y rechazó el cargo de forma definitiva (ej. fondos insuficientes)."""

    def __init__(self, detail: Any) -> None:
        self.detail = detail
        super().__init__(str(detail))


class CulqiResultAmbiguous(Exception):
    """
    No se pudo confirmar el resultado del cobro a tiempo (timeout, conexión perdida,
    respuesta inesperada). No implica que el cobro haya fallado — solo que no se sabe
    todavía. El llamador debe intentar reconciliar (find_payment) antes de decidir.
    """


class CulqiPythonClient:
    """Cliente servidor-a-servidor hacia culqi-python (ver POST /orders/{id}/pay)."""

    def __init__(self) -> None:
        self._base_url = settings.CULQI_PYTHON_BASE_URL
        self._api_key = settings.CULQI_PYTHON_SERVICE_API_KEY

    def _headers(self, *, idempotency_key: Optional[str] = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def create_charge(
        self,
        *,
        order_id: str,
        amount: int,
        currency_code: str,
        email: str,
        source_id: str,
        metadata: Optional[dict[str, str]] = None,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        """
        Ejecuta el cobro. Devuelve el response de Culqi (incluye `id` = culqi_charge_id)
        si fue exitoso.

        Lanza CulqiChargeRejected si Culqi respondió con un rechazo definitivo.
        Lanza CulqiResultAmbiguous si no se pudo confirmar el resultado a tiempo — el
        llamador (PayOrder) debe reconciliar con find_payment antes de decidir el estado
        final de la orden.
        """
        payload = {
            "amount": amount,
            "currency_code": currency_code,
            "email": email,
            "source_id": source_id,
            "order_id": order_id,
            "metadata": metadata or {},
        }
        idempotency_key = f"order-{order_id}-payment"

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
                response = await client.post(
                    "/api/culqi/charges",
                    json=payload,
                    headers=self._headers(idempotency_key=idempotency_key),
                )
        except (httpx.TimeoutException, httpx.TransportError):
            raise CulqiResultAmbiguous()

        if response.status_code == 200:
            return response.json()
        if response.status_code == 502:
            raise CulqiChargeRejected(response.json().get("detail"))
        # Cualquier otra respuesta inesperada (409 de idempotencia, 5xx propio, etc.)
        # se trata como ambigua — no asumimos éxito ni rechazo sin evidencia clara.
        raise CulqiResultAmbiguous()

    async def find_payments(self, *, order_id: str, timeout: float = 10.0) -> Optional[list[dict[str, Any]]]:
        """
        Reconciliación: consulta si ya existe un registro de pago para esta orden.
        Devuelve None si la consulta misma no pudo completarse (culqi-python sigue
        inalcanzable) — distinto de una lista vacía, que sí significa "no hay ningún
        intento registrado todavía".
        """
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
