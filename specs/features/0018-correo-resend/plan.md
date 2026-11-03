---
feature: 0018-correo-resend
spec: ./spec.md
---

# Plan — Correo saliente con Resend (fase 1)

## Enfoque

Módulo `app/modules/messaging` (agnóstico del canal; luego WhatsApp). Strategy: `BaseEmailProvider` (ABC) con
`send(message, sender, idempotency_key)`; `ResendEmailProvider` llama a `POST https://api.resend.com/emails` con
httpx async (el SDK oficial es síncrono). Factory por código de proveedor (`infra/factory.py`). La credencial se cifra
con Fernet (`app/core/crypto.py`, MultiFernet para rotar llaves) usando `CREDENTIALS_ENCRYPTION_KEY`.
Descartado: guardar en `general_settings` (mezcla secretos con parámetros visibles).

## Cambios por repo

### paku-backend
- `app/core/crypto.py`, `app/core/settings.py` (`CREDENTIALS_ENCRYPTION_KEY`), `requirements.txt` (`cryptography`).
- `app/modules/messaging/{domain,infra,app,api}`.
- Migración `4b5c6d7e8f9a` (`channel_providers`).

### paku-admin
- Configuración → Integraciones: tarjeta «Correo» real (`lib/services/integrations.ts`).

## Contrato

- `GET /admin/integrations/email` → `{provider, providers[{value,label}], enabled, configured, api_key_mask,
  from_email, from_name, reply_to, status, last_test_at, last_test_ok, last_test_error, encryption_ready, updated_at,
  updated_by}`.
- `PUT /admin/integrations/email` `{provider, enabled, api_key?, from_email, from_name, reply_to}` → igual que GET.
  422 `EMAIL_CONFIG_INVALID` (`field`), 503 `ENCRYPTION_UNAVAILABLE`.
- `POST /admin/integrations/email/test` `{to?}` → `{ok, to, provider_message_id, error}`. 409 `EMAIL_NOT_CONFIGURED`.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Perder la llave = perder las credenciales | Se vuelve a ingresar la API key; documentado. |
| Dominio no verificado en Resend | La prueba muestra el error de Resend. |

## Rompe clientes

- [x] paku-admin — impacto: ninguno (pantalla nueva).

## Tests

`tests/unit/test_email_integration.py`: cifrado y rotación, máscara, guardado y conservación de la key, validaciones,
503 sin llave, prueba con proveedor falso, petición y errores de Resend con `httpx.MockTransport`.

## Fase 2 — registro y reintentos

- `notification_logs` (migración `5c6d7e8f9a0b`): una fila por envío, `idempotency_key` única, `payload` con el
  mensaje armado para reintentar igual. `EmailSender.send` registra PENDING, intenta y deja SENT o FAILED; nunca lanza
  por fallas del proveedor. Reglas de reintento en `domain/logs.py`; job `retry_due_emails_job` cada minuto.
- Contrato: C-45. Tests: `tests/unit/test_email_sending.py`.
