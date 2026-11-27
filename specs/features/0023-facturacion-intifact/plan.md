---
feature: 0023-facturacion-intifact
spec: ./spec.md
---

# Plan — Facturación electrónica con Intifact

## Enfoque

Se reutiliza el módulo `app/modules/invoicing` (0020) y se reemplaza Nubefact por Intifact. La lógica sigue la que
ya funciona en `dulce-recuerdo-backend/app/modules/comprobantes`, adaptada a Paku: async, capas
`api / app / domain / infra`, configuración en base de datos (secretos cifrados con Fernet, como Resend) en lugar de
variables de entorno, y la orden pagada como origen del comprobante.

## Backend

- `domain/intifact.py`: reglas puras (series, clientes, líneas con descuento repartido, cuerpo de `/invoice/send`,
  firma del webhook, estados).
- `infra/intifact_client.py`: httpx async; `User-Agent` propio (Cloudflare).
- `infra/models.py`: `invoicing_providers` (más columnas), `invoicing_series`, `invoice_documents` (número único por
  ambiente, tipo y serie) e `invoicing_companies`. Migración `0b1c2d3e4f5a`.
- `app/config.py` (integración y prueba), `app/series.py`, `app/documents.py` (pendientes, vista previa, emisión,
  estado, anulación, archivos, registro, correo al cliente), `app/directory.py`, `app/accounting.py` (xlsx, zip y
  PLE con `openpyxl`) y `app/jobs.py` (revisión cada 10 minutos, emisión automática y webhook).
- Rutas: `/admin/integrations/intifact*` y `/admin/invoicing/*` (solo admin). Rutas públicas: `/invoicing/webhook`,
  `/invoicing/orders/{id}/documents` y `/invoicing/documents/{id}/pdf` (dueño de la orden). C-55.
- Se elimina el código de Nubefact y sus rutas (C-47).

## Admin (paku-admin)

- Configuración → Integraciones: la tarjeta de Nubefact se reemplaza por la de Intifact (key, RUC emisor, secreto del
  webhook, emisión automática, correo al cliente, prueba de conexión).
- Sección nueva «Facturación electrónica»: Por emitir, Comprobantes (registro y detalle con PDF, XML, CDR,
  actualizar y anular), Clientes, Series y Reportes contables.
- En el detalle de la orden: sus comprobantes y un acceso a emitir.

## Web (paku-web)

- Opcional: en el detalle de la orden, el comprobante con su PDF (`/invoicing/orders/{id}/documents`).

## Riesgos

- Dos procesos del backend emitiendo a la vez podrían pedir el mismo correlativo: el candado es por proceso y la
  restricción única de la tabla lo detecta. Hoy corre un solo contenedor.
- Sin webhook (plan Gratis) el estado llega con la revisión cada 10 minutos.
- El enlace público del PDF en el correo usa `/public/consultar/...` de la documentación de Intifact: verificarlo con
  la cuenta real.
- Anulación: mientras SUNAT no resuelve el resumen o la baja, el comprobante queda ANULANDO. Si SUNAT rechaza la
  anulación, queda en ANULANDO y hay que revisarlo en el portal de Intifact.

## Tests

`tests/unit/test_invoicing_intifact.py` (SQLite en memoria, Intifact simulado con `httpx.MockTransport`).
