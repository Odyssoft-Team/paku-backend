# App Paku Groomer — cambios por saldo de peso y pagos (2026-10-12)

Para: dev front de la app Paku Groomer. Changelog completo: `docs/cambios-api-para-front.md` (C-23 y C-24).
Feature: `specs/features/0003-saldo-por-peso/`.

## Resumen

El groomer **solo registra el peso** de la mascota en el servicio. Si ese peso da un precio mayor, el
backend guarda la diferencia en la orden y avisa al cliente y a los admins. **El admin** revisa y genera
el cobro; el cliente lo paga desde su app o la web. La app del groomer no cobra nada.

## Lo que tienes que cambiar

### 1. Peso que se muestra en la parada

`GET /orders/my-assignments` y `GET /orders/my-assignments/{id}`: `pet.weight_kg` ahora es el **peso
declarado al comprar**, no el peso actual de la mascota. Si el cliente cambió el peso después, no aplica
a esa orden.

- Muéstralo como **"Peso declarado"**.
- En órdenes anteriores a este cambio viene el peso actual (no se guardó el de la compra).

### 2. Registrar el peso (sin cambios de endpoint)

Sigue igual: `POST /pets/{pet_id}/records` con `type: "weight_record"` y `data: { weight_kg }`.

- El peso queda en la orden que estás atendiendo (en servicio, en camino o aceptada, en ese orden).
- La respuesta trae `price_check` (`old_price`, `new_price`, `difference`) o `null`.
  - `difference > 0`: puedes mostrar "El peso registrado sube el precio en S/ X; el admin lo revisará".
  - `difference <= 0` o `null`: no hay nada que cobrar (si el peso baja no se devuelve dinero).
- Si registras otra vez antes de que el admin genere el cobro, el último peso reemplaza al anterior.

### 3. Ya no llames a `create-adjustment` ⚠️

`POST /orders/{id}/create-adjustment` ahora es **solo admin**: el groomer recibe **403**. Si la app tiene
un botón o modal para "generar cobro adicional", quítalo.

### 4. Campos nuevos en la orden (opcionales)

`OrderOut` (y por lo tanto la parada) trae:

| Campo | Qué es |
|-------|--------|
| `declared_weight_kg` | peso con que se cotizó (null en órdenes antiguas) |
| `measured_weight_kg`, `measured_weight_at` | peso que registraste y cuándo |
| `extra_charge` | monto extra si el precio subió; null si no |
| `adjustment_order_id` | cobro ya generado por el admin |

Útil para mostrar "Peso registrado: 17 kg" en la parada después de pesar.

## Si la app también tiene modo cliente (mismo código)

- **Mascotas:** `weight_locked: true` en `GET /pets` y `GET /pets/{id}` mientras la mascota tenga un
  servicio solicitado. Deshabilita el botón de registrar o editar peso. Si igual se envía, el backend
  responde **409 `PET_WEIGHT_LOCKED`**.
- **Saldo:** `GET /orders/pending-balance` → `{ amount, currency, orders }`. Con `amount > 0`, muestra el
  aviso y deja pagar cada orden de `orders` con `POST /orders/{id}/pay` (tarjeta guardada, tarjeta nueva o
  Yape). Mientras haya saldo, `POST /holds` y `POST /orders` responden **409 `PENDING_BALANCE`**.
- **Órdenes de ajuste** (`parent_order_id` no nulo): son el saldo, no un servicio. No muestres
  seguimiento, chat ni pasos; su único ítem es `kind: "price_adjustment"`.
- **Pago (`POST /orders/{id}/pay`):** dos errores nuevos en los que el backend asegura que **no hubo
  cobro** y la orden sigue `pending`, así que se puede reintentar:
  - **502 `PAYMENT_PROVIDER_ERROR`**: no se pudo procesar.
  - **409 `PAYMENT_3DS_REQUIRED`**: el banco pide 3D Secure, que aún no se soporta; sugerir otra tarjeta
    o Yape.

  Muestra `detail.message`. No los trates como "resultado desconocido".

## Notificaciones nuevas

| `type` | A quién | Cuándo |
|--------|---------|--------|
| `weight_difference` | cliente y admins | el peso registrado sube el precio |
| `pending_balance` | cliente | el admin generó el cobro |

`data.order_id` apunta a la orden del servicio (`weight_difference`) o a la orden de ajuste
(`pending_balance`).

## Cómo probar

1. Mascota de 15 kg; el cliente compra un servicio y paga.
2. El cliente intenta cambiar el peso → bloqueado.
3. El groomer ve "15 kg" en la parada; registra 17 kg → `price_check.difference = 5`.
4. El admin ve "Diferencia de peso · S/ 5" en Órdenes y genera el cobro.
5. El cliente ve el saldo, no puede reservar y lo paga; luego puede reservar de nuevo.
