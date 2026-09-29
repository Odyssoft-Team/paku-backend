---
feature: 0001-wallet-culqi-customer
spec: ./spec.md
---

# Plan — Customer de proveedor y alta de tarjeta desde Wallet

## Enfoque

Mantener la API de Wallet como entrada pública autenticada. El repositorio crea y confirma una reserva `provisioning` única antes de la llamada externa; solo la solicitud que inserta esa fila crea Customer. Una respuesta válida actualiza la reserva a `ready`; un resultado ambiguo conserva la reserva y bloquea reintentos de Customer. El adaptador compartido de Culqi vive en `app/core`; Alembic administra el mapping y el índice parcial de IDs de Card.

## Cambios por repo

### paku-backend
- Módulo(s): `wallet`; integración HTTP compartida en `app/core` (con shim temporal de compatibilidad en `orders/infra`).
- Endpoints modificados: `POST /wallet/cards` cambia a recibir el token de tarjeta, conserva autenticación Paku y deriva la identidad únicamente de `CurrentUser`.
- Modelo / migración Alembic: `user_payment_customers`, FK a `users`, unique `(user_id, provider)`, estado provisioning/ready y timestamps; índice parcial único `(provider, culqi_card_id)`.
- Casos de uso (`app/`): orquestación crear/reutilizar Customer, crear Card y guardar `wallet_cards`.

### paku-web / paku-admin / paku-vet-dev
- Sin cambios en esta tarea. El request de `POST /wallet/cards` requiere coordinación de contrato antes de desplegar el cambio.

## Contrato

- Request de `POST /wallet/cards`: `{ "token_id": "tkn_test_..." }`.
- `user_id` y Customer ID no son campos de entrada.
- Response: `CardOut` con ID local, usuario autenticado, provider, `payment_method_id`, marca, últimos cuatro, expiración, estado default y fecha. No expone `culqi_customer_id` ni `culqi_card_id`; `payment_method_id` permanece porque el cliente actual lo usa como source para pagar.
- Rechazo externo explícito se normaliza como `502`; timeout/respuesta ambigua devuelve `503` y conserva una reserva `provisioning` de Customer.
- Fallo al guardar `wallet_cards` después de crear Card devuelve `503`; la fila externa no puede reconciliarse automáticamente con el contrato actual.

## Migraciones de datos

Crear tabla sin backfill: el historial existente de Customer IDs en `wallet_cards` no permite reconstruir de forma segura una relación canónica para usuarios con varias tarjetas. Downgrade elimina índices y tabla nueva; no toca `users` ni `wallet_cards`.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| El proveedor crea Customer pero falla persistencia o se pierde la respuesta | La reserva durable bloquea creación duplicada automática; queda en `provisioning` para reconciliación operativa. |
| Dos solicitudes concurrentes crean Customer para el mismo usuario | UNIQUE funciona como reserva: el ganador confirma `provisioning` antes de HTTP; el perdedor lee la fila existente y no llama al proveedor. |
| El proveedor crea Card pero se pierde respuesta o falla wallet commit | El índice parcial evita duplicar localmente el mismo provider/card ID; no evita un segundo ID remoto ni permite consultar la Card perdida. |
| Datos previos duplicados en wallet_cards | El índice único parcial puede fallar al desplegar; auditar duplicados existentes antes de aplicar la migración. |
| La API cambia antes de que el cliente web envíe token | No tocar web por alcance; documentar el nuevo contrato y la coordinación necesaria. |

## Rompe clientes

- [x] paku-web — el request antiguo de `POST /wallet/cards` cambia; coordinación requerida, sin editar el repo en esta tarea.
- [ ] paku-admin — impacto: ninguno identificado.
- [ ] paku-vet-dev — impacto: ninguno identificado.

## Tests

Pruebas unitarias del caso de uso para creación/reutilización, outcomes ambiguos, concurrencia, errores de persistencia y origen de identidad; inspección de constraints del modelo; validación de migración Alembic sin aplicar cambios a una base de datos configurada.