# Pendientes de pagos y Culqi

Se corrigen al final de la etapa 1 (decisión del dueño, 2026-10-03). Ninguno está resuelto todavía.
Rutas relativas a `paku-backend/`.

## Críticos

1. **`POST /orders/{id}/confirm-payment` marca la orden como pagada con cualquier texto.**
   Lo puede llamar el dueño de la orden; no se verifica el cargo contra Culqi/culqi-python.
   (`app/modules/orders/api/router.py`, `PostgresOrderRepository.confirm_payment`).
   Propuesta: solo admin, y verificando el cargo en culqi-python.
2. **`POST /orders/{id}/fail-payment` funciona desde cualquier estado de pago.** Con
   `paid → failed → retry-payment` el `culqi_charge_id` vuelve a `null` y la orden vuelve a
   `pending`, quedando lista para cobrarse otra vez. (`PostgresOrderRepository.fail_payment`).
   Propuesta: solo desde `pending`/`verifying` y solo backend/admin.

## Altos

3. **Clave de idempotencia fija por orden** (`order-{id}-payment` en `app/core/culqi_client.py`).
   Si culqi-python cachea la respuesta por esa clave, el reintento tras un pago fallido (otro token)
   devolvería el mismo rechazo. Verificar el comportamiento en culqi-python; propuesta: incluir el
   número de intento en la clave.
4. **`PayOrder` no rechaza órdenes canceladas** ni montos 0.
5. **Cargo extra por peso repetible.** `POST /orders/{id}/create-adjustment` compara contra la orden
   original sin descontar ajustes ya creados: llamarlo dos veces genera dos cargos.
   (Quién puede llamarlo se corrige en la fase 1; la duplicación queda aquí.)
6. **Pago en efectivo** (`confirm-cash-payment`): no valida el estado del servicio de la orden.

## Para revisar

7. URL canónica de culqi-python (web usa `stream.dev-qa.site/payment`, groomer usa `culqi-backend-*.run.app`) — ver `specs/workspace.md`.
8. Unificar la captura de tarjeta entre web (form propio) y app (SDK de Culqi en WebView).
