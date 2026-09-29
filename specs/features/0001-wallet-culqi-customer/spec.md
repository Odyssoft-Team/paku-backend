---
feature: 0001-wallet-culqi-customer
estado: in-progress
repos: [paku-backend]
creado: 2026-09-28
---

# Customer de proveedor y alta de tarjeta desde Wallet

## Problema

La operación de crear un Customer y asociarle una tarjeta parte actualmente del cliente. Paku no posee de forma persistente la asociación entre su usuario y el Customer externo, lo que deja la fuente de verdad de Wallet fuera del backend.

## Objetivo

Hacer que Paku autentique y orqueste el alta de tarjeta, mantenga la asociación usuario-proveedor-Customer y persista la tarjeta asociada al usuario autenticado.

## Fuera de alcance

- Cambios en `paku-web` y `culqi-python`.
- Tokenizar datos de tarjeta en Paku; el cliente seguirá entregando un token no sensible.
- Eliminar o sincronizar tarjetas del lado del proveedor.
- Incorporar otros proveedores en esta implementación.

## Comportamiento esperado

1. **Dado** un usuario autenticado sin Customer asociado al proveedor, **cuando** agrega una tarjeta con un token válido, **entonces** Paku crea el Customer, guarda la asociación, asocia la tarjeta con ese Customer y persiste la tarjeta en su wallet.
2. **Dado** un usuario autenticado con Customer asociado, **cuando** agrega otra tarjeta con un token válido, **entonces** Paku reutiliza el Customer existente y no crea otro.
3. **Dado** una solicitud que incluye `user_id` u otro identificador de Customer controlado por el cliente, **cuando** se procesa, **entonces** el usuario y Customer se determinan desde la identidad autenticada y el repositorio Paku.
4. **Dado** un fallo del proveedor al crear el Customer o Card, **cuando** se procesa el alta, **entonces** Paku no guarda una tarjeta incompleta y devuelve un error de proveedor.
5. **Dado** un Customer creado correctamente, **cuando** se repite el alta para el mismo usuario/proveedor, **entonces** la restricción persistente impide más de una asociación.
6. **Dado** que el resultado remoto de crear Customer es ambiguo, **cuando** llega un retry, **entonces** la reserva `provisioning` impide crear otro Customer hasta reconciliación.
7. **Dado** un ID de Culqi Card ya persistido, **cuando** se intenta guardar de nuevo con el mismo proveedor e ID, **entonces** la restricción única evita duplicar la fila local.

## Criterios de aceptación

- [ ] Existe una asociación persistente extensible por proveedor, única por usuario/proveedor y con FK a users.
- [ ] `POST /wallet/cards` exige JWT Paku y toma `user_id` solo de la identidad autenticada.
- [ ] El cliente entrega el token de tarjeta; no decide Customer ID ni datos visibles persistidos.
- [ ] El caso de uso reutiliza o crea Customer mediante el servicio de pagos, crea Card y persiste el método en el wallet.
- [ ] La migración Alembic tiene upgrade y downgrade reproducibles.
- [ ] Los tests cubren creación, reutilización, errores de proveedor y aislamiento de identidad.
- [ ] Resultados externos ambiguos quedan explícitos y no disparan creación automática duplicada de Customer.

## Impacto en el dominio

Wallet: nueva asociación PaymentCustomer y nuevo flujo de alta de Card. No cambia el modelo de usuario IAM ni el estado de órdenes.

La reconciliación automática de Customer/Card tras perder una respuesta no está disponible con el contrato actual del servicio de pagos. Las reservas pendientes bloquean el retry de Customer y requieren intervención operativa; el retry de Card continúa teniendo una ventana de duplicación externa.

## Preguntas abiertas

- [x] El token de tarjeta es responsabilidad de la capa cliente; el backend solo recibe el token.