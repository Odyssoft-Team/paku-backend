---
feature: 0020-boletas-nubefact
spec: ./spec.md
---

# Plan — Boletas con Nubefact (fase 1: conexión)

## Enfoque

Módulo nuevo `app/modules/invoicing` (separado de `messaging`: no es un canal de envío). Tabla
`invoicing_providers` (una fila por proveedor), token cifrado con Fernet como la API key de Resend
(`app/core/crypto.py`, ahora también con `mask_secret`). `NubefactClient` con httpx async. La prueba usa
`consultar_comprobante` sobre un número que nunca se emitirá. `readiness` junta RUC e IGV de Parámetros generales y
cuántos clientes activos tienen DNI.

## Cambios por repo

### paku-backend
- `app/modules/invoicing/{domain,infra,app,api}`; migración `6d7e8f9a0b1c`.
- `GET/PUT /admin/integrations/nubefact`, `POST /admin/integrations/nubefact/test` (C-47).

### paku-admin
- Tarjeta «Facturación electrónica · Nubefact» en Configuración → Integraciones.
- Vista `/dashboard/configuracion/integraciones/nubefact`: qué se puede, qué no y qué falta decidir.

## Fase 2 (pendiente de decisiones)

Tabla de comprobantes de Paku (serie, número, orden, estado SUNAT, enlaces), correlativo propio por serie,
`generar_comprobante` al evento elegido, consulta y anulación desde la orden, reintentos como en el correo.

## Tests

`tests/unit/test_invoicing_nubefact.py`: guardado cifrado y enmascarado, conservar token, validaciones (ruta https o
localhost, serie B, token), prueba de conexión con los códigos 24/10/11/51/500 y sin red (verifica que solo se
consulta), conteo de clientes con DNI.
