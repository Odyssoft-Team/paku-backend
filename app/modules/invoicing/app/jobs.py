"""Procesos automáticos de facturación electrónica (feature 0023) y el webhook de Intifact.

- Revisión periódica: consulta los comprobantes en curso (por si el webhook no está configurado o se perdió un aviso)
  y avisa al cliente de los aceptados.
- Emisión automática (si está activa): boletas de las órdenes listas (al realizarse el servicio o al confirmarse el
  pago, según la configuración) que no necesitan datos del admin.
- Webhook: firma HMAC-SHA256 de "{timestamp}.{cuerpo}", tolerancia de 5 minutos. A un aviso válido siempre se
  responde 200, aunque no sea de un comprobante nuestro: Intifact reintenta los errores y desactiva el endpoint tras
  20 fallos seguidos.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException

from app.modules.invoicing.app.config import ActiveIntifact, active_intifact, webhook_secret
from app.modules.invoicing.app.documents import (
    CustomerInput,
    IssueDocument,
    Notifier,
    apply_status,
    maybe_notify_customer,
    pending_rows,
)
from app.modules.invoicing.domain.intifact import (
    ANULANDO,
    BOLETA,
    STATUS_BY_EVENT,
    WEBHOOK_TOLERANCE_MS,
    valid_signature,
)
from app.modules.invoicing.infra.intifact_client import IntifactError

logger = logging.getLogger(__name__)

AUTO_ISSUE_BATCH = 20


async def refresh_in_progress(repo, intifact: ActiveIntifact, notifier: Optional[Notifier]) -> int:
    updated = 0
    for doc in await repo.documents_in_progress():
        try:
            await apply_status(repo, doc, await intifact.client.document(doc.provider_id))
            updated += 1
        except IntifactError:
            logger.warning("No se pudo consultar el comprobante %s-%s", doc.series, doc.number)
    for doc in await repo.accepted_not_notified():
        await maybe_notify_customer(repo, doc, intifact, notifier)
    return updated


async def auto_issue(repo, intifact: ActiveIntifact, notifier: Optional[Notifier]) -> tuple[int, int]:
    """Emite boletas de las órdenes listas sin comprobante que se pueden emitir solas. (emitidas, omitidas)"""
    if not intifact.auto_issue:
        return 0, 0
    orders, _ = await repo.pending_orders(limit_all=True, trigger=intifact.issue_trigger)
    issued = skipped = 0
    for row in await pending_rows(repo, orders):
        if issued >= AUTO_ISSUE_BATCH:
            break
        # Con un intento fallido no se reintenta solo: lo revisa el admin (evita quemar correlativos).
        if not row.auto_issuable or row.failed_attempts:
            skipped += 1
            continue
        try:
            await IssueDocument(repo=repo, intifact=intifact, notifier=notifier).execute(
                row.order_id, tipo=BOLETA, customer=CustomerInput(), actor_id=None)
            issued += 1
        except HTTPException as exc:
            skipped += 1
            logger.warning("Emisión automática de la orden %s omitida: %s", row.order_id, exc.detail)
    return issued, skipped


async def run_invoicing_jobs() -> None:
    """Scheduler (cada 10 minutos). Sin Intifact configurado y activo, no hace nada."""
    from app.core.db import AsyncSessionLocal
    from app.modules.invoicing.infra.postgres_invoicing_repository import PostgresInvoicingRepository
    from app.modules.messaging.app.sender import send_email

    try:
        async with AsyncSessionLocal() as session:
            repo = PostgresInvoicingRepository(session=session)
            try:
                intifact = await active_intifact(repo)
            except HTTPException:
                return

            async def notifier(**kw: Any) -> Any:
                return await send_email(session, **kw)

            updated = await refresh_in_progress(repo, intifact, notifier)
            issued, skipped = await auto_issue(repo, intifact, notifier)
            if updated or issued:
                logger.info("invoicing_jobs updated=%s issued=%s skipped=%s", updated, issued, skipped)
    except Exception:
        logger.exception("invoicing_jobs failed")


# ---------- Webhook ----------

def _unauthorized(message: str) -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "WEBHOOK_UNAUTHORIZED", "message": message})


@dataclass
class HandleWebhook:
    repo: Any
    notifier: Optional[Notifier] = None
    now_ms: Any = None   # tests

    async def execute(self, *, body: bytes, event_header: Optional[str], signature: Optional[str],
                      timestamp: Optional[str]) -> dict:
        secret = await webhook_secret(self.repo)
        if not secret:
            raise HTTPException(status_code=503, detail={"code": "WEBHOOK_NOT_CONFIGURED",
                                                         "message": "Webhook de facturación no configurado."})
        if not signature or not timestamp:
            raise _unauthorized("Falta la firma.")
        try:
            stamp = int(timestamp)
        except ValueError as exc:
            raise _unauthorized("Marca de tiempo inválida.") from exc
        now = self.now_ms() if self.now_ms else time.time() * 1000
        if abs(now - stamp) > WEBHOOK_TOLERANCE_MS:
            raise _unauthorized("Aviso vencido.")
        if not valid_signature(secret, timestamp, body, signature):
            raise _unauthorized("Firma inválida.")
        try:
            notice = json.loads(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "BAD_BODY", "message": "Cuerpo inválido."}) from exc
        event = (notice.get("event") if isinstance(notice, dict) else None) or event_header or ""
        data = (notice.get("data") if isinstance(notice, dict) else None) or {}

        if event == "webhook.test":
            return {"ok": True, "event": event}
        if event == "ticket.resolved":
            return {"ok": True, "event": event, "updated": await self._resolve_voids()}
        if event in STATUS_BY_EVENT:
            doc = await self._find(data)
            if doc is None:
                logger.info("Webhook %s de un comprobante que no es de Paku: %s", event, data.get("id"))
                return {"ok": True, "event": event, "document": None}
            await apply_status(self.repo, doc, {"sunat": {
                "estado": data.get("estado") or STATUS_BY_EVENT[event],
                "codigoRespuesta": data.get("codigoRespuesta"),
                "descripcionRespuesta": data.get("descripcionRespuesta") or data.get("ultimoError"),
            }, "hash": data.get("hash")})
            try:
                intifact = await active_intifact(self.repo)
                await maybe_notify_customer(self.repo, doc, intifact, self.notifier)
            except HTTPException:
                pass
            return {"ok": True, "event": event, "document": f"{doc.series}-{doc.number}"}
        logger.info("Webhook de facturación con evento no manejado: %s", event)
        return {"ok": True, "event": event}

    async def _find(self, data: dict):
        if data.get("id"):
            doc = await self.repo.document_by_provider_id(str(data["id"]))
            if doc:
                return doc
        if data.get("serie") and data.get("correlativo"):
            try:
                number = str(int(str(data["correlativo"])))
            except ValueError:
                return None
            return await self.repo.document_by_number(str(data["serie"]), number,
                                                      str(data["tipoDoc"]) if data.get("tipoDoc") else None)
        return None

    async def _resolve_voids(self) -> int:
        """ticket.resolved trae el id del resumen o la baja, no del comprobante: se consultan los que se anulan."""
        try:
            intifact = await active_intifact(self.repo)
        except HTTPException:
            return 0
        updated = 0
        for doc in await self.repo.documents_with_status(ANULANDO):
            try:
                await apply_status(self.repo, doc, await intifact.client.document(doc.provider_id))
                updated += 1
            except IntifactError:
                logger.warning("Webhook: no se pudo consultar el comprobante %s-%s", doc.series, doc.number)
        return updated
