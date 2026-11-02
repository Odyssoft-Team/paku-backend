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

## Fase 2 — envío y registro (pendiente)
## Fase 3 — plantillas Jinja2 (pendiente)
## Fase 4 — webhook y bajas (pendiente)
## Fase 5 — constructor visual (pendiente)
