---
feature: 0003-saldo-por-peso
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin, paku-web]
creado: 2026-10-12
---

# Saldo por diferencia de peso

## Problema

Pruebas de flujo del 2026-10-12 (servicio completo con la app del groomer):

- El precio se calcula con el peso que declara el cliente, pero la orden no guarda ese peso. El groomer
  ve el peso **actual** de la mascota: si el cliente lo cambió después de comprar (15 → 17 kg), el
  groomer ve 17 kg en un servicio cotizado con 15 kg.
- El cliente puede cambiar el peso en cualquier momento, incluso con un servicio en curso.
- Cuando el groomer pesa a la mascota y el peso da un precio mayor, el backend calcula la diferencia
  solo en la respuesta a quien registró el peso. El admin no se entera, y el cliente no tiene dónde ver
  ni pagar el saldo.
- El cargo extra se calcula con el peso actual de la mascota, no con el que midió el groomer, y se
  puede generar más de una vez para la misma orden.

## Objetivo

El groomer ve el peso con que se cotizó el servicio y registra el peso real. Si el precio sube, el
admin genera el cobro y el cliente lo paga antes de poder pedir otro servicio.

## Fuera de alcance

- Devoluciones: si el peso real da un precio menor, no se devuelve nada.
- Aprobación del admin para que el cliente cambie el peso.
- Cambios en la app del groomer (los hace el dev front con este contrato).
- Cobro automático con la tarjeta guardada: el cliente paga el saldo él mismo.

## Comportamiento esperado

1. **Dado** un cliente que compra un servicio para su mascota de 15 kg, **cuando** se crea la orden,
   **entonces** la orden guarda 15 kg como peso declarado.
2. **Dado** una orden con peso declarado de 15 kg y una mascota que hoy figura con 17 kg, **cuando** el
   groomer ve la parada, **entonces** ve 15 kg.
3. **Dado** una mascota con un servicio solicitado (pagado y sin terminar), **cuando** el cliente
   intenta registrar un peso, **entonces** recibe 409 `PET_WEIGHT_LOCKED`. La mascota trae
   `weight_locked: true` para que el front bloquee el botón.
4. **Dado** que el servicio terminó o se canceló, **entonces** la mascota vuelve a `weight_locked:
   false` y el cliente puede cambiar el peso.
5. **Dado** un groomer atendiendo la orden, **cuando** registra 17 kg y ese peso da un precio mayor,
   **entonces** la orden guarda el peso medido y el monto extra (S/5), el peso de la mascota pasa a
   17 kg, el cliente recibe un aviso de que hay un saldo por diferencia de peso y los admins reciben un
   aviso para revisarlo.
6. **Dado** el mismo caso con un peso que da un precio igual o menor, **entonces** se guarda el peso
   medido y se actualiza la mascota, sin monto extra ni avisos de cobro.
7. **Dado** una orden con monto extra, **cuando** el admin genera el cobro, **entonces** se crea una
   orden de ajuste por ese monto, el cliente recibe el aviso "Tienes un saldo por pagar" y la orden
   queda ligada a su ajuste.
8. **Dado** una orden que ya tiene su ajuste, **cuando** se intenta generar otro, **entonces** responde
   409 `ADJUSTMENT_EXISTS`.
9. **Dado** un cliente con un ajuste sin pagar, **cuando** intenta reservar cupo o crear una orden,
   **entonces** recibe 409 `PENDING_BALANCE`.
10. **Dado** un cliente con saldo, **cuando** paga el ajuste con tarjeta guardada, tarjeta nueva o
    Yape, **entonces** el saldo queda en cero y puede volver a pedir servicios.
11. **Dado** un ajuste que el admin decide perdonar, **cuando** lo cancela, **entonces** deja de contar
    como saldo.

## Criterios de aceptación

- [ ] La orden guarda el peso declarado al cotizar.
- [ ] La vista del groomer muestra el peso declarado (o el actual en órdenes antiguas sin ese dato).
- [ ] `weight_locked` en la mascota; el cliente no puede registrar peso mientras esté en `true`.
- [ ] El peso medido por el groomer o el admin queda en la orden, con el monto extra si el precio sube.
- [ ] Avisos al cliente y a los admins cuando hay monto extra.
- [ ] Solo el admin genera el cobro, una vez por orden, con el monto guardado.
- [ ] `GET /orders/pending-balance` devuelve el saldo del cliente.
- [ ] Con saldo pendiente no se puede reservar cupo ni crear órdenes.
- [ ] paku-admin: ver diferencia, generar el cobro y ver si se pagó.
- [ ] paku-web: peso bloqueado, saldo visible y pagable, reserva bloqueada con saldo.

## Impacto en el dominio

- **Orden:** nuevos datos `measured_weight_kg`, `measured_weight_at`, `extra_charge` y
  `adjustment_order_id`. El servicio base guarda `meta.pet_weight_kg` (peso declarado).
- **Mascota:** nueva regla: el dueño no cambia el peso con un servicio solicitado.
- **Cliente:** nueva regla: con saldo pendiente no puede pedir servicios.
- "Servicio solicitado" = orden de servicio (no de ajuste) con estado `created`, `accepted`,
  `on_the_way`, `in_service` o `skipped`, y pago `paid` o `verifying`. Las órdenes sin pagar no cuentan
  porque hoy nadie las limpia y bloquearían el peso para siempre.

## Preguntas abiertas

- [x] ¿Con una parada `skipped` el peso sigue bloqueado? Sí, el admin la reprograma (2026-10-12).
