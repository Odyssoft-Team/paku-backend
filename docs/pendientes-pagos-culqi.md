# Pendientes de pagos y Culqi

Revisado de nuevo el 2026-10-03 contra el código y `docs/arquitectura-actual-pagos.md`. Se corrigen al
final de la etapa 1. Ninguno está resuelto todavía. Rutas relativas a `paku-backend/`.

**Contexto:** el flujo normal funciona en desarrollo (guardar tarjeta → `POST /orders/{id}/pay` → cobro
servidor a servidor vía culqi-python → `paid`; reconciliación de `verifying` cada 5 min). Lo de abajo
no bloquea ese camino feliz: son abusos posibles llamando la API directamente, o casos que no se dan en
una prueba normal (tarjeta rechazada y reintento con otra).

## Decisiones del dueño (2026-10-03)

- `confirm-payment` y `fail-payment` **se quedan como están por ahora**: probablemente los usan paku-web
  o la app para registrar estados internos; no se tocan mientras funcionen (puntos 6 y 8 quedan en espera).
- **Efectivo:** la plataforma no contempla efectivo. El uso esperado de `confirm-cash-payment` es que un
  **admin** confirme un pago hecho fuera de la pasarela (ej. Yape directo). Hoy solo lo puede llamar el
  groomer asignado → ajustar cuando se retome pagos (punto 11).
- Punto 1 (reintento tras rechazo) **corregido en paku-backend** el 2026-10-03: la clave de idempotencia
  ahora es por orden + medio de pago. La parte de culqi-python (`outcome`) queda pendiente.

## Funcional (afecta a clientes reales) — verificado en el código de ambos repos

1. **Tras un rechazo, pagar con otra tarjeta deja la orden trabada en `verifying` para siempre.**
   - paku-backend usa la misma `Idempotency-Key` para todos los intentos (`order-{id}-payment`,
     `app/core/culqi_client.py`).
   - culqi-python (`app/core/idempotency.py`) cachea éxitos **y errores** 24 h y, si la misma clave llega
     con otro payload (otro `source_id`), responde **409** sin llamar a Culqi (`app/api/routes.py:212`).
   - paku-backend trata ese 409 como ambiguo → reconcilia con `GET /api/culqi/payments` → encuentra el
     rechazo anterior, pero `PaymentOut` **no trae `outcome`**, así que Paku no puede saber que fue un
     rechazo y deja la orden en `verifying`. El cronjob repite lo mismo cada 5 min y nunca la resuelve.
   - El cliente tampoco puede reintentar: `retry-payment` solo acepta órdenes `failed`.
   - **Corrección (dos repos):** paku-backend genera una clave por intento (`order-{id}-payment-{n}`);
     culqi-python guarda y devuelve `outcome` (`rejected` / `ambiguous`) en `payments` y `PaymentOut`.
2. **culqi-python guarda como `failed` también los errores de red/timeout con Culqi** (mismo `except
   CulqiApiError`), y además los cachea 24 h: un timeout en el que Culqi sí cobró queda registrado como
   fallo. Es lo que obliga a Paku a exigir `outcome` (punto 1).
3. **La idempotencia de culqi-python es en memoria** (`InMemoryIdempotencyStore`): se pierde al
   reiniciar y no se comparte entre instancias de Cloud Run. El propio código lo advierte. Mitiga que la
   clave también se envía a Culqi. Propuesta: Redis/Memorystore o tabla en su BD.
4. **El registro del pago en culqi-python es best-effort**: si su BD falla, el cobro ocurre pero la
   reconciliación de Paku no lo encuentra.

## Seguridad (requiere llamar la API a mano; la app no lo hace)

5. **A verificar en paku-web (alta prioridad):** `docs/arquitectura-actual-pagos.md` dice que paku-web
  todavía llama directo a culqi-python para guardar tarjetas, y `specs/workspace.md` menciona la variable
  `NEXT_PUBLIC_PAYMENT_API_KEY`. Las variables `NEXT_PUBLIC_*` quedan **en el JavaScript del navegador**.
  Si esa es la API key de servicio de culqi-python, cualquiera puede llamar `POST /api/culqi/charges`
  (cobrar con cualquier `crd_*` guardado) o `GET /api/culqi/payments`. El diseño de culqi-python lo
  prohíbe (`docs/FRONTEND_INTEGRATION.md`). Si está expuesta: rotar la key y quitarla del front.

6. **`POST /orders/{id}/confirm-payment` marca la orden como pagada con cualquier texto.** Lo puede
   llamar el dueño de la orden; no verifica el cargo. El propio doc lo describe como "fallback, no es el
   flujo normal del web". **Decisión pendiente:** solo admin o eliminar.
7. **`POST /orders/{id}/pay` no verifica que una tarjeta `crd_*` sea del usuario** (punto 7 del doc de
   arquitectura). Explotarlo requiere conocer el `crd_*` de otro cliente (no se expone a terceros).
   Propuesta: si el `source_id` es `crd_*`, exigir que esté en `wallet_cards` del usuario.

## Consistencia de estados (no producen doble cobro)

8. **`POST /orders/{id}/fail-payment` funciona desde cualquier estado**, incluido `paid`; con
   `retry-payment` la orden vuelve a `pending` y pierde el `culqi_charge_id`. **No hay doble cobro**: al
   volver a pagar, la idempotencia de culqi-python devuelve el cargo original (o 409 → reconciliación →
   encuentra el éxito anterior). El daño es dejar el estado de pago incorrecto. Propuesta: solo desde
   `pending`/`verifying`; decidir si queda para admin.
9. **`PayOrder` no rechaza órdenes canceladas** (ni total 0). La app no ofrece pagar una cancelada.
10. **Cargo extra por peso repetible.** `POST /orders/{id}/create-adjustment` compara contra la orden
   original sin descontar ajustes previos: dos llamadas = dos cargos extra. (Desde C-03 solo lo puede
   hacer el groomer asignado o un admin.)
11. **Pago en efectivo** (`confirm-cash-payment`): el groomer asignado puede marcarlo en cualquier estado
   del servicio. **Decisión pendiente:** ¿solo el groomer, también admin, y en qué momento?

## Fuera de paku-backend (para coordinar)

12. `paku-web` todavía guarda tarjetas llamando directo a culqi-python (no a `POST /wallet/cards`) y
   tokeniza dos veces (puntos 6 y 10 del doc de arquitectura).
13. URL canónica de culqi-python (web usa `stream.dev-qa.site/payment`, groomer usa `culqi-backend-*.run.app`).
14. Unificar la captura de tarjeta entre web (form propio) y app (SDK de Culqi en WebView).

## Menor

15. `app/modules/wallet/app/use_cases.py`: `SetDefaultCard` tiene un `return card` duplicado (código muerto).
