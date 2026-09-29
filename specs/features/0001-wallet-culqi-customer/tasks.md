---
feature: 0001-wallet-culqi-customer
plan: ./plan.md
---

# Tasks — Customer de proveedor y alta de tarjeta desde Wallet

## Backend
- [x] Implementar entidad, modelo y repositorio PaymentCustomer con reserva `provisioning`.
- [x] Mover el cliente Culqi a infraestructura compartida y agregar outcomes ambiguos.
- [x] Orquestar Customer/Card desde `POST /wallet/cards` con identidad autenticada.
- [x] Corregir cadena Alembic y agregar índices únicos de mapping y tarjeta.
- [x] Añadir tests unitarios de flujo, errores, identidad, concurrencia y persistencia.
- [x] Actualizar contrato y documentar estados que requieren reconciliación manual.

## Frontend
- [x] Sin cambios en esta tarea; coordinar el contrato nuevo antes del despliegue.

## Cierre
- [ ] Spec a estado `done`.
- [x] Índices de dominio y features actualizados.
- [x] Ejecutar pruebas disponibles y revisar diff.