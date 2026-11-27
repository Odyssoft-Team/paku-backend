---
feature: 0023-facturacion-intifact
plan: ./plan.md
---

# Tasks — Facturación electrónica con Intifact

## Backend
- [x] 1. Dominio Intifact, cliente HTTP y modelos; migración `0b1c2d3e4f5a`.
- [x] 2. Integración: guardar (cifrado), leer (enmascarado) y probar la conexión sin emitir.
- [x] 3. Series con correlativo inicial y una activa por tipo.
- [x] 4. Pendientes, vista previa y emisión (boleta o factura), con el correo al cliente.
- [x] 5. Registro, detalle, actualizar estado, anular, PDF, XML y CDR.
- [x] 6. Directorio de clientes de facturación y empresas.
- [x] 7. Reportes contables (resumen de totales y de facturas, compendio de PDF, registro de ventas PLE 14.1).
- [x] 8. Webhook firmado, revisión cada 10 minutos y emisión automática opcional.
- [x] 9. Endpoints del cliente (comprobantes de su orden y PDF).
- [x] 10. Retirar Nubefact (código, rutas y tests). Tests (`tests/unit/test_invoicing_intifact.py`). C-55.
- [x] 10b. Momento de emisión (`issue_trigger`: al realizarse el servicio o al pagar), «Por emitir» y emisión
  automática según él, y emisión de varias (`POST /admin/invoicing/issue-batch`). Migración `1c2d3e4f5a6b`. C-55.

## Admin
- [x] 11. Integraciones: tarjeta de Intifact en lugar de Nubefact.
- [x] 12. Sección Facturación electrónica: Por emitir, Comprobantes, Clientes, Series y Reportes.
- [x] 12c. Por emitir: selección y «Emitir seleccionadas» con resumen; Intifact: momento de emisión.
## Web (paku-web)
- [x] 12b. Detalle de la orden: comprobante con su PDF (`/invoicing/orders/{id}/documents`).


## Cierre
- [ ] 13. Migración en el servidor; configurar la key `fact_test_`, el RUC sandbox y las series; emitir una boleta y
  una factura de prueba y anularlas. Verificar el enlace público del PDF.
- [ ] 14. Pasar a `fact_live_` con las series reales (correlativo inicial si ya se usaron).
