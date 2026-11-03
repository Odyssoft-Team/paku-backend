---
feature: 0018-correo-resend
plan: ./plan.md
---

# Tasks — Correo saliente con Resend

## Fase 1
- [x] 1. Cifrado (`app/core/crypto.py`) y variable `CREDENTIALS_ENCRYPTION_KEY`.
- [x] 2. Dominio, `ResendEmailProvider`, factory, tabla `channel_providers` y migración `4b5c6d7e8f9a`.
- [x] 3. `GET/PUT /admin/integrations/email` y `POST /admin/integrations/email/test`.
- [x] 4. Tests (`tests/unit/test_email_integration.py`).
- [x] 5. C-44 en `docs/cambios-api-para-front.md`.
- [x] 6. Admin: tarjeta «Correo» en Configuración → Integraciones.
- [ ] Cierre fase 1: llave en el servidor, migración, dominio verificado y prueba real desde el admin.

## Fase 2 — envío y registro
- [x] 1. Tabla `notification_logs` (migración `5c6d7e8f9a0b`) y repositorio.
- [x] 2. `EmailSender` / `send_email(...)`: idempotencia, PENDING → SENT/FAILED, la clave también a Resend.
- [x] 3. Reintentos: fallas temporales a 1, 5, 15 y 60 min (máx. 5), PENDING colgados; job cada minuto.
- [x] 4. `GET /admin/notification-logs` y `POST /admin/notification-logs/{id}/retry`; la prueba queda registrada.
- [x] 5. Tests (`tests/unit/test_email_sending.py`). C-45.
- [x] 6. Admin: tarjeta «Envíos de correo» (estado, búsqueda, fechas, reintentar).
- [ ] Cierre fase 2: migración en el servidor y revisar el registro tras la prueba real.

## Fase 3 — plantillas Jinja2 (pendiente)
## Fase 4 — webhook y bajas (pendiente)
## Fase 5 — constructor visual (pendiente)
