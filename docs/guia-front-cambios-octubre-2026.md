# Guía para el front — cambios del backend (octubre 2026)

Para: equipos de la **app de clientes**, la **app Paku Groomer** y la **web admin**.
Fecha: 2026-10-04. Entorno: desarrollo (ya desplegado).

Esta guía resume **qué cambió y qué tiene que hacer cada app**. El detalle técnico de cada cambio
(códigos, ejemplos completos) está en [`cambios-api-para-front.md`](cambios-api-para-front.md), entradas
**C-01 a C-15**. Las preguntas que tenemos para ustedes están en
[`consultas-para-front.md`](consultas-para-front.md).

---

## 1. Lo que rompe a todas las apps

### 1.1 "ally" ahora es "groomer" (C-09)

| Antes | Ahora |
|---|---|
| rol `"ally"` | rol `"groomer"` |
| `ally_id` (órdenes, asignación, streaming) | `groomer_id` |
| `?ally_id=` en `GET /admin/orders` | `?groomer_id=` |
| `ally_location` (tracking) | `groomer_location` |
| `sender_role: "ally"` (chat) | `"groomer"` |
| `recorded_by_role: "ally"` (historial de mascota) | `"groomer"` |

Las rutas no cambian (`/orders/my-assignments`, `/accept`, `/depart`, `/arrive`, `/complete`, `/tracking/...`).
Los tokens ya emitidos con `role: "ally"` siguen funcionando hasta que expiren.

### 1.2 Estado nuevo de orden: `skipped` (C-13)

Todas las apps deben reconocer `status: "skipped"` (parada saltada). No asuman una lista cerrada de estados.
Estados actuales: `created`, `accepted`, `on_the_way`, `in_service`, `done`, `cancelled`, `skipped`.

### 1.3 `GET /pets/{id}` pide token (C-04)

Enviar siempre `Authorization: Bearer`. Responde al dueño, al groomer asignado a una orden activa de esa
mascota o a un admin.

---

## 2. App de clientes

### 2.1 Flujo de compra nuevo (C-07, C-15)

```
1. Elegir mascota (debe tener peso; sin peso no hay precio)
2. Ver servicios y precios         GET /store/categories/{slug}/products?pet_id=...   (con token)
3. Ver detalle y complementos      GET /store/products/{id}?pet_id=...                (con token)
4. (opcional) Cotizar              POST /store/quote
5. Ver días con cupo               GET /availability?service_id=...&date_from=YYYY-MM-DD
6. RESERVAR el día                 POST /holds                      ← nuevo paso obligatorio
7. Armar el carrito con hold_id    POST /cart/items
8. Checkout                        POST /cart/{id}/checkout
9. Crear la orden                  POST /orders
10. Pagar                          POST /orders/{id}/pay
```

**Regla de la reserva:** el cupo queda bloqueado mientras el cliente compra. La reserva dura **2 horas**
(lo mismo que el carrito) y, una vez en el carrito, **vence junto con él**. Al crear la orden se confirma y
ya no vence. Si el carrito vence, la reserva también: hay que **volver a elegir la fecha**.

#### Paso 6 — Reservar

```http
POST /holds
{ "pet_id": "…", "service_id": "<id del servicio>", "date": "2026-10-10" }
```
Respuesta `201`: `{ id, user_id, pet_id, service_id, status: "held", expires_at, created_at, date }`.

| Error | Qué significa | Qué hacer |
|---|---|---|
| 409 `no_availability` / `no_capacity` | Ese día no tiene cupo | Mostrar otro día |
| 409 `HOLD_ALREADY_EXISTS` | La mascota ya tiene reserva ese día (`detail.hold_id`) | Reusar esa reserva |
| 422 `DATE_IN_PAST` | Fecha pasada | Elegir otra fecha |
| 403 `PET_NOT_OWNED` | La mascota no es del usuario | — |

Para recuperar reservas (ej. si se cierra la app): **`GET /holds`** devuelve las del usuario.

#### Paso 7 — Carrito

```json
POST /cart/items
{ "items": [
  { "kind": "service_base", "ref_id": "<id del servicio>",
    "meta": { "pet_id": "…", "hold_id": "<id de la reserva>", "scheduled_time": "10:00" } },
  { "kind": "service_addon", "ref_id": "<id del complemento>" }
] }
```

- **`meta.hold_id` es obligatorio** en el servicio base. `meta.scheduled_date` ya no hace falta (sale de la
  reserva; si la envían, debe coincidir).
- **Complementos:** una línea `service_addon` por complemento, sin `meta`. Solo existen junto a un servicio
  base y el backend valida que sean de ese servicio y aptos para la mascota.
- **Precios:** el backend calcula `unit_price` y `name`. Lo que envíen se ignora. Si enviaron un precio
  distinto, el ítem vuelve con `price_adjusted: true` y `client_unit_price`. **Mostrar siempre el
  `unit_price` de la respuesta.**
- Quitar el servicio base (`DELETE /cart/{id}/items/{item_id}`) o reemplazarlo (`PUT /cart/{id}/items`)
  por otra reserva **libera** la reserva anterior.
- No se venden productos físicos (`kind: "product"` → 422 `PRODUCT_NOT_SUPPORTED`).

| Error del carrito (`detail.code`) | Qué hacer |
|---|---|
| `HOLD_REQUIRED` (400) | Reservar antes (paso 6) |
| `HOLD_EXPIRED` (409) | **Volver a elegir fecha** (nueva reserva) |
| `HOLD_MISMATCH` (409) | La reserva no es de ese servicio/mascota/fecha (`detail.fields`) |
| `HOLD_NOT_FOUND` (404) / `HOLD_NOT_OWNED` (403) | Reserva inválida: volver al paso 6 |
| `BASE_SERVICE_REQUIRED`, `MULTIPLE_BASE_SERVICES`, `DUPLICATE_ADDON` (400) | Corregir el armado |
| 422 `"Pet weight_kg is required to quote"` | Pedir el peso de la mascota |

#### Paso 8 — Checkout

- **409 `HOLD_EXPIRED`** → volver a elegir fecha.
- **409 `PRICE_CHANGED`** → los precios cambiaron desde que se agregó (regla de precio o peso). El carrito ya
  quedó con los precios nuevos; mostrar `detail.items` (`old_unit_price` → `new_unit_price`) y `detail.total`,
  y volver a llamar a checkout.

#### Paso 9 — Orden

`POST /orders { "cart_id": "…", "address_id": "…" }`. Si la reserva venció → **409 `HOLD_EXPIRED`**. La orden
trae `hold_id`.

#### Paso 10 — Pago

Sin cambios de contrato. Ahora, si una tarjeta es rechazada, el cliente **sí puede reintentar con otra
tarjeta** (antes la orden quedaba trabada en `verifying`).

### 2.2 Seguimiento del servicio

- La orden trae campos nuevos: `service_step` (`reception`, `bath`, `drying`, `finishing`, `return`),
  `service_steps_log`, `addons_done`, y si se saltó la parada: `skip_reason`, `skip_note`, `skipped_at`.
- Notificaciones nuevas: "Tu groomer llegó" (al recoger), una por cada paso, "<complemento> realizado",
  demoras ("Tu groomer llegará ~X min más tarde") y parada saltada.
- Fotos del servicio: `GET /orders/{id}/photos` → `[{ id, kind, read_url, note, created_at }]`.
- Demoras: `GET /orders/{id}/delay-reports`.
- Mapa: `/tracking/orders/{id}/current` y `/route` ahora devuelven `groomer_location`. Recomendamos llamar
  `/route` cada 30–60 s (consume la API de Google) y `/current` para mover el punto.

### 2.3 Otros

- El cliente **ya no puede cambiar el estado** de su orden (`PATCH /orders/{id}` → 403).
- Catálogo con `?pet_id=`: requiere token y que la mascota sea del usuario; solo muestra servicios y
  complementos aptos para su raza.

---

## 3. App Paku Groomer

### 3.1 Ruta del día (pedido 2 — C-10)

- `GET /orders/my-assignments?date=YYYY-MM-DD` (hora de Lima), ordenado por `scheduled_at` (orden de ruta).
- **Nuevo** `GET /orders/my-assignments/{id}` (403 si la orden es de otro groomer).
- Ambos devuelven además `pet`, `client` (`first_name`, `last_name`, `phone`) y `service` (`name`,
  `addons: [{id, name}]`).

### 3.2 Proceso del servicio (pedido 3 — C-11) ⚠️ cambia el cierre

```
/depart → /arrive (queda en "reception")
  → foto "initial" (obligatoria)
  → POST /orders/{id}/next-step { "from_step": "reception" } → bath
  → next-step → drying → next-step → finishing
     (marcar complementos en bath/drying/finishing: POST /orders/{id}/addons/{addon_id}/done)
  → next-step (exige todos los complementos hechos) → return
  → POST /orders/{id}/complete   ← solo desde "return"
```

Errores 409 (`detail.code`): `STEP_MISMATCH` (doble tap), `INITIAL_PHOTO_REQUIRED`, `ADDONS_PENDING`
(`detail.addons`), `LAST_STEP` (usar `/complete`), `NOT_IN_SERVICE`, `SERVICE_STEPS_PENDING` (al completar
antes de `return`), `ADDON_NOT_ALLOWED_NOW`.

### 3.3 Fotos (pedido 6 — C-12)

1. `POST /media/signed-upload { "entity_type": "order", "entity_id": "<order_id>", "content_type": "image/jpeg" }`
2. Subir el archivo a `upload_url`.
3. `POST /orders/{id}/photos { "object_name": "…", "kind": "initial" | "final" | "incident", "note"? }`

### 3.4 Saltar parada (pedido 4 — C-13)

`POST /orders/{id}/skip { "reason": "pet_not_present" | "tutor_not_present" | "other", "note"? }` — en
camino, o recién llegado (paso `reception`). La orden queda `skipped`, se avisa al cliente y a los admins,
se corta el tracking y **se libera el cupo del día**.

### 3.5 Demora (pedido 5 — C-14)

`POST /orders/{id}/delay-report { "delay_minutes": 1-180, "note"? }` — con `accepted` u `on_the_way`.

### 3.6 Otros

- Cambios de estado y cargo extra por peso: solo sobre **sus** órdenes (403 en otras).
- Ya puede leer la ficha de la mascota de su parada (`GET /pets/{id}`).

---

## 4. Web admin

- **Renombre groomer** (sección 1.1): rol, `groomer_id`, filtro `?groomer_id=`.
- **Asignar** (`POST /admin/orders/{id}/assign`): body `{ "groomer_id", "scheduled_at", "notes"? }`. Sobre una
  orden `skipped` la reprograma: vuelve a `created` y reinicia el proceso del servicio.
- **Cancelar** (`POST /admin/orders/{id}/cancel`): también acepta `skipped`; **libera el cupo** del día.
- **Cupos:**
  - **Nuevo** `GET /admin/availability/{slot_id}/holds` — quién reservó ese día (con estado).
  - Crear un cupo repetido → 409 `SLOT_EXISTS`; servicio inexistente → 404 `SERVICE_NOT_FOUND`.
  - Bajar la capacidad por debajo de lo reservado → 409 `CAPACITY_BELOW_BOOKED`.
  - `GET /availability` sin `date_from` empieza hoy en hora de Lima.
- Avisos nuevos para admins: paradas saltadas y demoras reportadas.
- Fotos y demoras de cada orden: `GET /orders/{id}/photos`, `GET /orders/{id}/delay-reports`.

---

## 5. Checklist por app

**Clientes**
- [ ] Renombre `ally` → `groomer`
- [ ] Reservar (`POST /holds`) antes del carrito y enviar `meta.hold_id`
- [ ] Manejar `HOLD_EXPIRED` → volver a elegir fecha
- [ ] Complementos como líneas `service_addon` sin `meta`
- [ ] Mostrar `unit_price` del backend y manejar `PRICE_CHANGED`
- [ ] Token en `GET /pets/{id}` y en el catálogo con `pet_id`
- [ ] Reconocer `skipped` y mostrar `service_step`, fotos y demoras

**Groomer**
- [ ] Renombre `ally` → `groomer`
- [ ] Ruta del día con `?date=` y detalle de parada
- [ ] Pasos con `next-step`, foto inicial, complementos y `/complete` solo desde `return`
- [ ] Fotos, saltar parada y demoras

**Admin**
- [ ] Renombre `ally` → `groomer` (incluye `groomer_id` al asignar)
- [ ] Reconocer `skipped` y reprogramar/cancelar
- [ ] Ver reservas por día y manejar los nuevos errores de cupos
