---
feature: 0003-saldo-por-peso
spec: ./spec.md
---

# Plan — Saldo por diferencia de peso

## Enfoque

La orden pasa a ser la dueña de los datos de peso: guarda el peso declarado al cotizar y el peso medido
en el servicio, con el monto extra ya calculado. El admin genera el cobro desde ese monto guardado, no
desde el peso actual de la mascota, y la orden apunta a su ajuste, lo que impide un segundo cobro. El
saldo es la suma de los ajustes sin pagar; se consulta en un endpoint y bloquea la reserva de cupo y la
creación de órdenes.

Descartado: seguir derivando todo de `pets.weight_kg`. Es el origen del problema (el dato cambia
después de la compra).

## Cambios por repo

### paku-backend

- **cart** (`pricing.py`): al cotizar el servicio base, guardar `meta.pet_weight_kg` (peso usado).
- **orders**
  - Modelo + migración: columnas `measured_weight_kg`, `measured_weight_at`, `extra_charge`,
    `adjustment_order_id` en `orders`. Se exponen en `OrderOut`.
  - `groomer_view.py`: `pet.weight_kg` = `meta.pet_weight_kg` de la orden; si falta (orden antigua), el
    actual.
  - Repo: `find_order_for_measurement(pet_id, groomer_id | None)` reemplaza a
    `find_recalculation_candidate`. Busca la orden de servicio de la mascota con estado `in_service`,
    `on_the_way` o `accepted` (en ese orden de prioridad); si quien registra es un groomer, solo entre
    sus órdenes. Ya no exige `paid` (cubre efectivo).
  - Repo: `set_measured_weight(...)`, `set_adjustment_order(...)`, `has_requested_service(pet_id)`,
    `list_unpaid_adjustments(user_id)`.
  - `adjustment.py`: solo admin; toma `extra_charge` de la orden; 409 `NO_EXTRA_CHARGE` si no hay,
    409 `ADJUSTMENT_EXISTS` si ya hay ajuste. `pet_id` del body pasa a opcional (se ignora).
  - Nuevo `GET /orders/pending-balance` → `{amount, currency, orders: [OrderOut]}`.
  - Guarda `PENDING_BALANCE` en `POST /orders`.
- **pet_records** (`create_record.py`)
  - Dueño + `weight_record` + mascota con servicio solicitado → 409 `PET_WEIGHT_LOCKED`.
  - Groomer/admin + `weight_record`: si hay orden para medir y aún no tiene ajuste, guarda peso medido
    y `extra_charge` (`difference` si > 0, si no `null`). Con monto extra: aviso al cliente y a los
    admins. Se mantiene `price_check` en la respuesta (compatibilidad).
- **pets**: `PetOut.weight_locked` (bool) en `GET /pets` y `GET /pets/{id}`.
- **booking**: guarda `PENDING_BALANCE` en `POST /holds`.

### paku-admin

- Órdenes: badge "Diferencia de peso" (hay `extra_charge`, sin ajuste) y "Saldo pendiente" (ajuste sin
  pagar).
- Detalle de orden: peso declarado vs. medido, monto extra, botón "Generar cobro"
  (`create-adjustment`) y estado de pago del ajuste.
- `PriceCheckDialog`: deja de mandar `pet_id`; maneja 409 `ADJUSTMENT_EXISTS` / `NO_EXTRA_CHARGE`.

### paku-web

- Mascotas: botón de registrar/editar peso deshabilitado con `weight_locked`, con el motivo.
- Saldo: aviso en la cuenta y en el inicio de reserva con `GET /orders/pending-balance`; pago del ajuste
  con el flujo de pago existente (tarjeta guardada, nueva o Yape).
- Reserva: bloqueada con saldo pendiente; maneja 409 `PENDING_BALANCE` y `PET_WEIGHT_LOCKED`.
- Mis pedidos: las órdenes de ajuste se muestran como "Saldo por diferencia de peso".

### App del groomer (dev front, fuera de este trabajo)

- `pet.weight_kg` de `/orders/my-assignments` ahora es el peso declarado.
- Registrar el peso sigue igual (`POST /pets/{id}/records`); no debe llamar a `create-adjustment` (pasa
  a ser solo admin).

## Contrato

```
GET /orders/pending-balance
200 {"amount": 5.0, "currency": "PEN", "orders": [OrderOut, ...]}   // amount 0 y [] si no hay

OrderOut (+)
  measured_weight_kg: float | null
  measured_weight_at: datetime | null
  extra_charge: float | null        // monto a cobrar por peso; null si no hay
  adjustment_order_id: uuid | null  // ajuste generado

PetOut (+)
  weight_locked: bool

POST /orders/{id}/create-adjustment   (solo admin; body {} o {"pet_id"} ignorado)
  409 {"code": "NO_EXTRA_CHARGE"} | {"code": "ADJUSTMENT_EXISTS", "adjustment_order_id"}

POST /holds, POST /orders
  409 {"code": "PENDING_BALANCE", "message", "amount"}

POST /pets/{id}/records (dueño, type=weight_record)
  409 {"code": "PET_WEIGHT_LOCKED", "message"}
```

## Migraciones de datos

Una migración Alembic con 4 columnas nulas en `orders`. Reversible. Sin backfill: las órdenes antiguas
no tienen peso declarado y usan el actual como respaldo.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| La app del groomer llama hoy a `create-adjustment` y pasa a recibir 403 | El flujo acordado es que el admin lo revisa; avisar al dev front |
| Órdenes viejas con varias abiertas para la misma mascota | Prioridad por estado; si hay empate, la de `scheduled_at` más cercana |
| Cliente bloqueado por un ajuste generado por error | El admin cancela el ajuste (`POST /admin/orders/{id}/cancel`) |

## Rompe clientes

- [ ] paku-web — campos nuevos y errores 409 nuevos; se adapta en esta feature.
- [ ] paku-admin — `create-adjustment` cambia de reglas; se adapta en esta feature.
- [ ] app del groomer — significado de `pet.weight_kg` y `create-adjustment` solo admin.

## Tests

pytest de casos de uso: peso declarado en el snapshot, vista del groomer, bloqueo del dueño, medición
con y sin monto extra, ajuste único y solo admin, saldo pendiente y bloqueo de hold/orden.
