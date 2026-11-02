"""Resend por su API HTTP (https://resend.com/docs/api-reference/emails/send-email), con httpx async.

No se usa el SDK oficial de Python porque es síncrono y bloquearía el event loop.
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.modules.messaging.domain.email import BaseEmailProvider, EmailMessage, EmailProviderError, Sender, SendResult

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 15.0


class ResendEmailProvider(BaseEmailProvider):
    code = "resend"

    def __init__(self, api_key: str, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._api_key = api_key
        self._transport = transport  # solo tests

    async def send(self, message: EmailMessage, *, sender: Sender,
                   idempotency_key: Optional[str] = None) -> SendResult:
        body: dict = {"from": sender.formatted, "to": message.to, "subject": message.subject}
        if message.html is not None:
            body["html"] = message.html
        if message.text is not None:
            body["text"] = message.text
        if sender.reply_to:
            body["reply_to"] = sender.reply_to
        if message.tags:
            body["tags"] = [{"name": k, "value": v} for k, v in message.tags.items()]
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:256]

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.post(RESEND_URL, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise EmailProviderError(f"No se pudo conectar con Resend: {exc.__class__.__name__}.",
                                     retryable=True) from exc

        if response.status_code >= 400:
            raise EmailProviderError(_error_message(response), status_code=response.status_code,
                                     retryable=response.status_code == 429 or response.status_code >= 500)
        try:
            message_id = response.json().get("id")
        except ValueError:
            message_id = None
        return SendResult(provider_message_id=message_id)


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
        detail = data.get("message") or data.get("name")
    except ValueError:
        detail = None
    return f"Resend respondió {response.status_code}" + (f": {detail}" if detail else ".")
