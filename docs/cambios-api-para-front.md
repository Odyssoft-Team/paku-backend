# Cambios de API — para los fronts

Lista de cambios del backend que afectan a la app de clientes, la app Paku Groomer y la web admin.
Cada entrada indica si **rompe** (el front debe cambiar antes o junto con el despliegue) o es
**compatible** (el front puede adaptarse cuando quiera).

Formato de cada entrada:

- **Endpoint(s)**
- **Qué cambia**
- **Rompe / Compatible**
- **Qué debe hacer el front**
- **Apps afectadas**

Las entradas se agregan al final, en el orden en que se hacen. Fecha de inicio: 2026-10-03.
Ningún cambio está desplegado hasta que se indique lo contrario.

---

## C-01 · Errores de cambio de estado ya no devuelven 500

- **Endpoints:** `PATCH /orders/{id}`, `POST /orders/{id}/status`
- **Qué cambia:** orden inexistente → **404**; transición hacia atrás o inválida → **409**;
  `PATCH` sin `status` → **400**. Antes los tres casos respondían **500** por un bug.
- **Compatible.** Si el front trataba el 500 como error genérico, ahora puede mostrar el motivo.
- **Apps:** Groomer, Admin.

## C-02 · Solo admin o groomer asignado cambian el estado de una orden

- **Endpoints:** `PATCH /orders/{id}`, `POST /orders/{id}/status`
- **Qué cambia:**
  - `PATCH /orders/{id}`: antes lo podía usar **el cliente dueño** sobre su orden (podía marcarla
    como `done`). Ahora responde **403** a clientes.
  - `POST /orders/{id}/status`: antes cualquier groomer podía cambiar **cualquier** orden. Ahora solo
    la orden que tiene asignada (403 si no). Admin sigue pudiendo cambiar cualquiera.
- **Rompe** solo si la app de clientes usaba `PATCH /orders/{id}` (ver `consultas-para-front.md` #1).
- **Qué hacer:** la app de clientes no debe cambiar estados; la app Groomer debería usar los
  endpoints semánticos (`/accept`, `/depart`, `/arrive`, `/complete`).
- **Apps:** Clientes (si usaba PATCH), Groomer, Admin.

## C-03 · Cargo extra por peso: solo el groomer de esa orden

- **Endpoint:** `POST /orders/{id}/create-adjustment`
- **Qué cambia:** antes cualquier groomer podía crear el cargo extra sobre cualquier orden. Ahora solo
  el groomer asignado a esa orden o un admin; los demás reciben **403**.
- **Compatible** para el uso normal (el groomer ajusta su propia orden).
- **Apps:** Groomer, Admin.

## C-04 · `GET /pets/{id}` exige sesión (pedido 1)

- **Endpoint:** `GET /pets/{id}`
- **Qué cambia:** antes era público (cualquiera con el UUID veía la mascota y su foto). Ahora exige
  `Authorization: Bearer` y solo responde al **dueño**, al **groomer asignado** a una orden activa
  de esa mascota o a un **admin**. Sin sesión → **401**; sin permiso → **403**.
- **Rompe** si alguna app llamaba sin token.
- **Qué hacer:** enviar siempre el token. La app Groomer ya puede leer la ficha de la mascota de su parada.
- **Apps:** todas.

## C-05 · Catálogo con `?pet_id=` solo para el dueño de la mascota

- **Endpoints:** `GET /store/categories/{slug}/products?pet_id=`, `GET /store/products/{id}?pet_id=`,
  `POST /store/quote`
- **Qué cambia:** sin `pet_id` el catálogo sigue siendo público. Con `pet_id` (precios para esa
  mascota) ahora exige sesión y que la mascota sea del usuario (o admin): sin sesión → **401**,
  mascota ajena → **403**.
- **Rompe** si la app consultaba precios con `pet_id` sin enviar el token.
- **Qué hacer:** enviar el token cuando se use `pet_id`.
- **Apps:** Clientes.

## C-06 · Reservas: cupos que se liberan y reservas que solo maneja su dueño

- **Endpoints:** `POST /holds/{id}/confirm`, `POST /holds/{id}/cancel`, `GET /availability`
- **Qué cambia:**
  - Confirmar o cancelar una reserva ajena → **403** (antes cualquier usuario podía). Admin puede todas.
  - Cancelar una reserva **sí devuelve el cupo** del día (antes no se guardaba).
  - Las reservas que vencen (10 min sin confirmar) **devuelven su cupo** (antes lo perdían para siempre).
    `GET /availability` ahora refleja los cupos liberados.
- **Compatible** para el uso normal (cada cliente maneja sus propias reservas).
- **Apps:** Clientes, Admin.

## C-07 · El carrito usa los precios del backend

- **Endpoints:** `POST /cart/items`, `POST /cart/{id}/items`, `PUT /cart/{id}/items`, `POST /cart/{id}/checkout`
- **Qué cambia:**
  - El `unit_price` y el `name` de cada ítem los calcula el backend con `store` (la misma lógica que
    `POST /store/quote`: especie, raza y peso de la mascota). Lo que envíe el front se **acepta y se
    ignora**. Cada ítem de la respuesta trae dos campos nuevos:
    - `price_adjusted`: `true` si el precio enviado no coincidía con el del servidor.
    - `client_unit_price`: el precio que envió el front (solo cuando `price_adjusted` es `true`).
  - **Formato único de addons:** cada complemento es una línea `kind: "service_addon"` con
    `ref_id` = id del addon. No necesita `meta`; el backend lo liga al único servicio base del carrito y
    le completa `meta.pet_id`. `meta.requires_base`, `meta.base_service_id` y `meta.addon_ids` se
    aceptan y se ignoran.
    ```json
    { "kind": "service_base",  "ref_id": "<id del servicio>", "meta": { "pet_id": "…", "scheduled_date": "2026-10-10", "scheduled_time": "10:00" } }
    { "kind": "service_addon", "ref_id": "<id del addon>" }
    ```
  - Validaciones nuevas al agregar (también en `POST /cart/{id}/items`, que antes no validaba nada):

    | Caso | Respuesta |
    |---|---|
    | Producto físico (`kind: "product"`) | 422 `{"code": "PRODUCT_NOT_SUPPORTED"}` |
    | Addon sin servicio base en el carrito | 400 `{"code": "BASE_SERVICE_REQUIRED"}` |
    | Addon repetido | 400 `{"code": "DUPLICATE_ADDON"}` |
    | Más de un servicio base | 400 `{"code": "MULTIPLE_BASE_SERVICES"}` |
    | Mascota de otro usuario | 403 `{"code": "PET_NOT_OWNED"}` |
    | Mascota sin `pet_id` / inexistente | 400 `PET_REQUIRED` / 404 `PET_NOT_FOUND` |
    | Mascota sin peso | 422 `"Pet weight_kg is required to quote"` (igual que quote) |
    | Servicio de otra especie o raza no permitida | 400 (mismo mensaje que quote) |
    | Addon de otro servicio / no apto para la mascota / sin precio | 400/422 `{"addon_id", "reason"}` (igual que quote) |

  - **Checkout recotiza.** Si un precio cambió desde que se agregó (cambio de regla o de peso), el
    carrito se actualiza con los precios nuevos y el checkout responde **409**:
    ```json
    { "detail": { "code": "PRICE_CHANGED",
                  "message": "Los precios del carrito cambiaron. Revisa el nuevo total y confirma de nuevo.",
                  "items": [ { "item_id": "…", "name": "Baño completo", "old_unit_price": 60.0, "new_unit_price": 65.0 } ],
                  "total": 80.0, "currency": "PEN" } }
    ```
    El front muestra el nuevo total y vuelve a llamar a checkout (la segunda vez pasa).
- **Rompe** si la app enviaba productos físicos, addons de otro servicio, o mascotas sin peso
  (antes pasaban con el precio que mandara el front).
- **Qué hacer:** mostrar siempre `unit_price` de la respuesta (no el calculado localmente); manejar
  `PRICE_CHANGED` en el checkout; tomar los precios a mostrar de `GET /store/...?pet_id=` o `POST /store/quote`.
- **Apps:** Clientes.

## C-08 · Catálogo y cotización filtran por raza permitida

- **Endpoints:** `GET /store/categories/{slug}/products?pet_id=`, `GET /store/products/{id}?pet_id=`, `POST /store/quote`
- **Qué cambia:** con `pet_id`, el listado solo muestra servicios disponibles para la raza de la mascota
  y el detalle solo los addons aptos (especie y raza). `POST /store/quote` responde **400** si el
  servicio o un addon no aplica a esa raza (`"reason": "not_for_this_pet"` en addons). Antes se mostraban
  y cotizaban igual. Sin `pet_id` no cambia nada.
- **Compatible** (la app recibe menos opciones, todas comprables).
- **Apps:** Clientes.

## C-09 · "ally" pasa a llamarse "groomer" en toda la API ⚠️ despliegue coordinado

- **Qué cambia (nombres viejos → nuevos):**

  | Dónde | Antes | Ahora |
  |---|---|---|
  | Rol de usuario (token, `GET /users/me`, `/admin/users`, `PATCH /admin/users/{id}/role`, `POST /admin/users`, `?role=`) | `"ally"` | `"groomer"` |
  | `OrderOut` (todas las respuestas de órdenes) | `ally_id` | `groomer_id` |
  | `POST /admin/orders/{id}/assign` (body y respuesta) | `ally_id` | `groomer_id` |
  | `GET /admin/orders?…` (filtro) | `?ally_id=` | `?groomer_id=` |
  | `GET /tracking/orders/{id}/current` y `/route` | `ally_location` | `groomer_location` |
  | Chat: `sender_role` de los mensajes | `"ally"` | `"groomer"` |
  | Historial de la mascota: `recorded_by_role` (y filtro `?recorded_by_role=`) | `"ally"` | `"groomer"` |
  | `GET /streaming/orders/{id}/session` (respuesta) | `ally_id` | `groomer_id` |
  | Textos de error | "ally" | "groomer" |

  Los endpoints (rutas) no cambian: `/orders/my-assignments`, `/orders/{id}/accept`, `/depart`,
  `/arrive`, `/complete`, `/tracking/...` siguen iguales.
- **Datos:** la migración `1a2b3c4d5e6f` renombra columnas y convierte los valores guardados
  (usuarios, mensajes, historial). Corre sola al desplegar (el contenedor ejecuta `alembic upgrade head`).
- **Sesiones abiertas:** un token emitido antes del despliegue con `role: "ally"` se acepta como
  `groomer` hasta que expire; el groomer no necesita volver a iniciar sesión.
- **Rompe** a las 3 apps: deben leer los nombres nuevos **el mismo día** del despliegue del backend.
- **Qué hacer:** reemplazar `ally_id` → `groomer_id`, `ally_location` → `groomer_location` y el valor
  de rol `"ally"` → `"groomer"` en todo el front.
- **Apps:** todas.

## C-10 · Ruta del groomer: filtro por día, detalle y datos de la parada (pedido 2)

- **Endpoints:**
  - `GET /orders/my-assignments?date=YYYY-MM-DD&status=` — `date` es opcional y filtra `scheduled_at`
    en **hora de Lima**. Orden: `scheduled_at` ascendente (orden de ruta definido por el admin).
  - **Nuevo** `GET /orders/my-assignments/{id}` — una parada; solo el groomer asignado (o admin).
    403 si la orden es de otro groomer, 404 si no existe.
- **Qué cambia:** ambas respuestas son `OrderOut` + tres campos nuevos: `pet` (id, name, species,
  breed_name, sex, birth_date, weight_kg, photo_url firmada, notes, skin_sensitivity, bath_behavior,
  tolerates_drying, tolerates_nail_clipping, special_shampoo), `client` (first_name, last_name, phone)
  y `service` (name, addons: [{id, name}]). Cualquiera puede ser `null` si falta el dato.
- **Compatible** (campos agregados).
- **Apps:** Groomer.

## C-11 · Proceso del servicio paso a paso y complementos realizados (pedido 3)

- **`OrderOut`** suma: `service_step` (string|null), `service_steps_log` ([{step, started_at}]) y
  `addons_done` ([{addon_id, done_at}]). Pasos fijos: `reception` → `bath` → `drying` → `finishing` → `return`.
- `POST /orders/{id}/arrive`: además deja `service_step = "reception"`. La notificación ahora dice
  **"Tu groomer llegó — Tu groomer llegó para recoger a tu mascota."**
- **Nuevo** `POST /orders/{id}/next-step` (groomer asignado o admin; `status = in_service`),
  body `{ "from_step": "<paso actual>" }`. Avanza un paso y notifica al cliente
  (`data: {order_id, status, service_step}`). Errores **409** con `detail.code`:
  `STEP_MISMATCH` (from_step ≠ paso actual), `LAST_STEP` (en `return`: usar `/complete`),
  `INITIAL_PHOTO_REQUIRED` (desde reception sin foto `initial`), `ADDONS_PENDING` (desde finishing con
  complementos sin realizar; `detail.addons` los lista), `NOT_IN_SERVICE`.
- **Nuevo** `POST /orders/{id}/addons/{addon_id}/done` (groomer asignado o admin; en bath, drying o
  finishing). Idempotente. 404 si el addon no está en la orden; 409 `ADDON_NOT_ALLOWED_NOW` fuera de esos pasos.
  Notifica "<nombre> realizado" (`data: {order_id, addon_id}`).
- `POST /orders/{id}/complete`: exige `service_step = "return"` → si no, **409** `SERVICE_STEPS_PENDING`.
  Excepción de transición: órdenes que ya estaban en servicio antes del despliegue (sin `service_step`)
  se pueden completar.
- **Rompe** la app Groomer actual: para completar ahora debe recorrer los pasos.
- **Apps:** Groomer (y Clientes, que puede mostrar el paso actual).

## C-12 · Fotos del servicio (pedido 6)

- `POST /media/signed-upload` acepta `entity_type: "order"` (groomer asignado o admin). Genera
  `orders/{order_id}/photo_….jpg`.
- `POST /media/signed-read` con un `orders/…`: groomer asignado, cliente dueño o admin.
- `POST /media/confirm-profile-photo` con `entity_type: "order"` → **400**: las fotos de orden se
  registran con el endpoint siguiente.
- **Nuevo** `POST /orders/{id}/photos` (groomer asignado o admin), body
  `{ "object_name", "kind": "initial" | "final" | "incident", "note"? }` → 201 `{ id, kind, read_url, note, created_at }`.
  403 si el `object_name` no es de esa orden.
- **Nuevo** `GET /orders/{id}/photos` (groomer asignado, cliente dueño o admin) → lista en orden de creación.
- La foto `initial` es obligatoria para avanzar desde `reception` (C-11).
- **Compatible** (todo nuevo).
- **Apps:** Groomer, Clientes, Admin.

## C-13 · Saltar parada: estado `skipped` (pedido 4)

- **Nuevo** `POST /orders/{id}/skip` (groomer asignado o admin), body
  `{ "reason": "pet_not_present" | "tutor_not_present" | "other", "note"? }`. Solo con `on_the_way`, o
  `in_service` en el paso `reception`; si no → **409** `SKIP_NOT_ALLOWED`.
  La orden queda `status: "skipped"` con `skip_reason`, `skip_note`, `skipped_at` (campos nuevos de
  `OrderOut`). Notifica al cliente y a todos los admins (`data: {order_id, status, skip_reason}`).
  El tracking se detiene (solo acepta `on_the_way`/`in_service`). Sigue apareciendo en `my-assignments`.
- `POST /admin/orders/{id}/assign` sobre una orden `skipped`: vuelve a `created`, limpia `service_step`,
  `service_steps_log` y `addons_done`, y la reprograma con el nuevo `scheduled_at`. `skip_*` se conservan
  como historial.
- `POST /admin/orders/{id}/cancel` también acepta órdenes `skipped` (supuesto, ver plan).
- `GET /admin/orders?status=skipped` funciona.
- **Rompe** si alguna app trata `status` como una lista cerrada: **todas deben reconocer `skipped`**.
- **Apps:** Groomer, Clientes, Admin.

## C-14 · Avisos de demora (pedido 5)

- **Nuevo** `POST /orders/{id}/delay-report` (groomer asignado o admin; con `accepted` u `on_the_way`),
  body `{ "delay_minutes": 1–180, "note"? }` → 201 `{ id, order_id, groomer_id, delay_minutes, note, created_at }`.
  Notifica al cliente ("Tu groomer llegará ~X min más tarde") y a los admins. 409 `DELAY_NOT_ALLOWED` en otro estado.
- **Nuevo** `GET /orders/{id}/delay-reports` (groomer asignado, cliente dueño o admin).
- **Compatible** (todo nuevo).
- **Apps:** Groomer, Clientes, Admin.

## C-15 · Reserva de cupo ligada a la compra ⚠️ (2026-10-04)

Regla: el cliente **reserva el cupo del día antes de comprar**; el cupo queda bloqueado mientras compra,
se confirma al crear la orden y se libera si la compra no se concreta o la orden se cancela.

- `POST /holds` — la reserva ahora dura **2 horas** (lo mismo que el carrito; antes 10 min). Nuevas reglas:
  fecha pasada → 422 `DATE_IN_PAST`; mascota de otro usuario → 403 `PET_NOT_OWNED`; la mascota ya tiene
  reserva vigente ese día → 409 `HOLD_ALREADY_EXISTS` (con `hold_id` de la existente).
- **Carrito** (`POST /cart/items`, `POST /cart/{id}/items`, `PUT /cart/{id}/items`): el servicio base
  **debe traer `meta.hold_id`**. `meta.scheduled_date` ya no es obligatoria: el backend la toma de la
  reserva (si se envía, debe coincidir). Desde ese momento la reserva **vence junto con el carrito**.
  Errores (`detail.code`): `HOLD_REQUIRED` (400), `HOLD_NOT_FOUND` (404), `HOLD_NOT_OWNED` (403),
  `HOLD_MISMATCH` (409, `detail.fields` dice si no coincide servicio, mascota o fecha),
  **`HOLD_EXPIRED` (409)**.
- Quitar el servicio base del carrito, o reemplazarlo por otro con otra reserva, **libera** la reserva anterior.
- `POST /cart/{id}/checkout` y `POST /orders`: si la reserva venció → **409 `HOLD_EXPIRED`**.
  **El front debe llevar al cliente a elegir la fecha de nuevo** (nueva reserva).
- `POST /orders` confirma la reserva y la guarda en `OrderOut.hold_id`; desde ahí ya no vence.
- `POST /admin/orders/{id}/cancel` y `POST /orders/{id}/skip` **liberan** el cupo del día. Al reprogramar
  una parada saltada, el admin asigna la nueva fecha a mano (no se toma otro cupo).
- `POST /holds/{id}/confirm` queda **obsoleto**: ya no cambia el estado (responde la reserva tal cual).
  La confirmación ocurre sola al crear la orden.
- **Nuevo** `GET /holds` — reservas del usuario, más recientes primero.
- **Nuevo** `GET /admin/availability/{slot_id}/holds` — quién reservó ese día (con estado).
- `GET /availability` sin `date_from` empieza en el **día de hoy en Lima** (antes, desde las 7 pm,
  empezaba en el día siguiente).
- Admin: crear un cupo que ya existe → 409 `SLOT_EXISTS`; servicio inexistente → 404 `SERVICE_NOT_FOUND`
  (antes 500); bajar la capacidad por debajo de lo reservado → 409 `CAPACITY_BELOW_BOOKED`.
- **Rompe** la app de clientes: hay que reservar antes de armar el carrito, enviar `meta.hold_id` y manejar
  `HOLD_EXPIRED`.
- **Apps:** Clientes, Admin.

## C-16 · Respuestas del front aplicadas (2026-10-05)

- **Eliminado** `PATCH /orders/{id}` (ninguna app lo usaba). Para cambiar estado: los endpoints semánticos
  del groomer (`/accept`, `/depart`, `/arrive`, `/next-step`, `/complete`) o `POST /orders/{id}/status`
  (admin o groomer asignado).
- `POST /orders/{id}/delay-report` ahora acepta también órdenes en **`created`** (además de `accepted` y
  `on_the_way`), para avisar demora a la siguiente parada.
- **Compatible.**
- **Apps:** Groomer.

## C-17 · Notificaciones al groomer (pedido del front, 2026-10-05)

Notificación + push (best-effort) al groomer cuando el admin cambia su ruta. Lo que el groomer mismo
dispara no se le notifica.

| Evento | A quién | `type` | title / body | data |
|---|---|---|---|---|
| `POST /admin/orders/{id}/assign`, orden sin groomer o con otro groomer | groomer nuevo | `order_assigned` | "Nueva parada asignada" / "Firulais · 10/10 10:00 · Barranco" | `{order_id, status, scheduled_at}` |
| Mismo `assign`, cambia de groomer | groomer anterior | `order_unassigned` | "Parada retirada de tu ruta" / "Firulais · 10/10 10:00 fue asignada a otro groomer" | `{order_id}` |
| `assign` con el mismo groomer y otra fecha, o la orden venía de `skipped` | groomer | `order_rescheduled` | "Parada reprogramada" / "Firulais pasa al 11/10 14:30" | `{order_id, status, scheduled_at}` |
| `POST /admin/orders/{id}/cancel`, si tenía groomer | groomer | `order_cancelled` | "Parada cancelada" / "Firulais · 10/10 10:00 fue cancelada" | `{order_id, status: "cancelled"}` |

- Fecha y hora en **hora de Lima**. El lugar es el distrito (o la dirección si no está en el catálogo).
- Reasignar con el mismo groomer y la misma fecha no envía nada al groomer.
- **Corrección:** el aviso al cliente "Servicio asignado" mostraba la hora en UTC (5 h adelantada); ahora
  usa hora de Lima.
- El push lleva además `data.type` (el mismo `type` de la notificación) para elegir ícono y navegación.
- **Compatible.**
- **Apps:** Groomer (y Clientes: la hora del aviso de asignación).

## C-18 · Push: arreglo y variable `PUSH_PROVIDER` (2026-10-05)

- **Bug corregido:** los push de notificaciones y de chat **nunca se enviaban, en ningún entorno** (ni en
  producción). El código abría la sesión de BD de una forma que fallaba siempre, y el error se descartaba
  sin dejar log. Ahora se envían y, si fallan, queda el error en el log.
- **Nueva variable** `PUSH_PROVIDER` = `expo` (push reales) | `mock` (solo log). Si no se define: `expo`
  en `ENV=production` y `mock` en el resto (igual que antes). Así se pueden probar push reales en el
  entorno de pruebas sin tocar `ENV`.
- El envío a Expo ya no bloquea la API mientras espera la respuesta de Expo.
- **Compatible.** Para recibir push en pruebas: `PUSH_PROVIDER=expo` en el `.env` del servidor.
- **Apps:** todas.

## C-19 · Arreglo: las respuestas de reservas daban 500 (reportado por el front, 2026-10-05)

- **Bug:** en el esquema `HoldOut`, el campo `date` tapaba al tipo `date` y quedaba tipado como `null`.
  Toda respuesta con una reserva fallaba con **500**: `POST /holds` (la reserva sí se guardaba y tomaba el
  cupo, por eso el reintento daba `409 HOLD_ALREADY_EXISTS`), `GET /holds`, `POST /holds/{id}/confirm`,
  `POST /holds/{id}/cancel` y `GET /admin/availability/{slot_id}/holds`.
- **Corregido:** `date` vuelve a ser `"YYYY-MM-DD"` en la respuesta y en `/openapi.json`. Sin cambios de
  contrato. Se agregó un test que revisa todos los esquemas de la API para que no vuelva a pasar.
- Las reservas que quedaron tomadas por el 500 se liberan solas al vencer (2 h), o el cliente las ve con
  `GET /holds` y puede reusarlas o cancelarlas.
- **Apps:** Clientes, Admin.

## C-20 · Aviso a los admins: nuevo pedido por asignar (2026-10-05)

- Cuando una orden **de servicio** (sin `parent_order_id`) pasa a `payment_status = "paid"` por
  `POST /orders/{id}/pay`, por la reconciliación de `verifying` o por `confirm-payment`, todos los admins
  reciben notificación + push:
  - `type`: `order_paid` · title: "Nuevo pedido por asignar"
  - body: `"<mascota> · <servicio> · <dd/mm> · <distrito>"` (el día reservado, **sin hora**: la pone el admin)
  - `data`: `{ order_id, scheduled_date }`
- No aplica a órdenes de ajuste ni a `confirm-cash-payment` (lo usa un admin, que ya sabe del pedido).
- Una orden creada sin pagar no genera aviso.
- **Compatible.** **Apps:** Admin.

## C-21 · El cupo sigue al día asignado, `reserved_date` y hora opcional (2026-10-05)

- **`POST /admin/orders/{id}/assign`** (regla de negocio: reprogramar lo pide el cliente y lo acepta el
  admin, sin que el cliente compre de nuevo). Se compara el día de `scheduled_at` (hora de Lima) con la
  **reserva vigente** (confirmada) de la orden:
  - mismo día → solo cambia la hora;
  - otro día → se toma cupo del día nuevo y se libera el del día original;
  - sin reserva vigente (p. ej. venía de `skipped` y el cupo se liberó) → se toma cupo del día elegido;
  - día sin cupo (o sin cupos habilitados) → **409 `NO_CAPACITY`**, sin cambiar nada:
    `{"code": "NO_CAPACITY", "message": "No hay cupos disponibles para el 11/10/2026. Elige otro día o amplía la capacidad.", "date": "2026-10-11"}`.
    El `message` está pensado para mostrarse tal cual.
- **`OrderOut.reserved_date`** (`"YYYY-MM-DD"` o `null`): día de la reserva vigente. Se actualiza al mover
  el cupo y pasa a `null` si el cupo se libera (orden cancelada o parada saltada). `hold_id` se conserva
  como historial. Las órdenes existentes se rellenan con la migración `4d5e6f7a8b9c`.
- **Carrito:** `meta.scheduled_time` del servicio base ahora es **opcional** (el cliente no elige hora). Si
  se envía, se valida el formato `HH:MM`.
- **Push (Android):** los push se envían con `sound: "default"`, `priority: "high"` y
  `channel_id: "default"`. La app debe crear el canal `"default"` con importancia alta.
- **Compatible** (campos agregados; validación relajada). El 409 `NO_CAPACITY` en `assign` es nuevo.
- **Apps:** Admin, Clientes, Groomer.

## C-22 · Búsqueda de direcciones: sugerencias y ubicación real (2026-10-07)

- **Endpoints nuevos** (todos con sesión, `Authorization: Bearer`):
  - `GET /geo/places/autocomplete?q=&district_id=&session_token=` →
    `[{ "place_id", "main_text", "secondary_text" }]`. Con menos de 3 letras devuelve `[]` sin costo.
    Máximo 5 sugerencias de Perú, priorizando el distrito enviado.
  - `GET /geo/places/{place_id}?session_token=` →
    `{ "place_id", "lat", "lng", "formatted_address", "address_line", "building_number", "district_id", "district_name", "district_active" }`.
    `district_id` es el de `GET /geo/districts` (o `null` si no coincide ninguno); `district_active: false`
    si Paku aún no atiende ese distrito.
  - `GET /geo/geocode?q=&district_id=` → `{ "lat", "lng" }`. Respaldo cuando no se eligió sugerencia.
- **`session_token`:** la app genera uno por formulario de dirección (UUID) y lo envía en autocomplete y
  en el detalle de la sugerencia elegida; así Google cobra la búsqueda como una sola sesión.
- **Errores:** 404 `GEO_NOT_FOUND`, 422 `DISTRICT_NOT_FOUND`, 429 `GEO_RATE_LIMITED` (límite por
  usuario), 503 `GEO_UNAVAILABLE` (sin clave configurada, Google caído o sin cuota). Con 429/503 la app
  debe seguir funcionando como antes: sin sugerencias y con el pin en el centro del distrito.
- **Servidor:** requiere `GOOGLE_PLACES_API_KEY` (Places API (New) + Geocoding). Límites ajustables con
  `GEO_AUTOCOMPLETE_PER_MINUTE` (60), `GEO_AUTOCOMPLETE_PER_DAY` (300), `GEO_LOOKUP_PER_DAY` (30) y
  `GEO_CACHE_TTL_SECONDS` (86400). Sin la clave, solo estos endpoints responden 503.
- **Compatible** (solo endpoints nuevos; `GET /geo/districts` no cambia).
- **Apps:** Clientes. Spec: `specs/features/0002-busqueda-direcciones/`.

## C-23 · Pago: errores que no cobran ya no dejan la orden en `verifying` (2026-10-12)

- **Endpoint:** `POST /orders/{id}/pay`
- **Qué cambia:** antes, cualquier respuesta de culqi-python que no fuera cobro ni rechazo explícito
  dejaba la orden en `verifying` para siempre. Ahora:
  - **502 `PAYMENT_PROVIDER_ERROR`** si culqi-python rechaza la petición antes de llamar a Culqi
    (validación 422, API key, etc.). La orden **sigue `pending`**: no hubo cobro y se puede reintentar.
  - **409 `PAYMENT_3DS_REQUIRED`** si Culqi pide 3D Secure (responde 200 sin cargo). La orden sigue
    `pending`. El 3DS todavía no está soportado: el cliente debe usar otra tarjeta o Yape.
  - `antifraud_details` se recortan a los límites de culqi-python (dirección de máximo 100 caracteres,
    teléfono de máximo 15, etc.), que antes podían provocar el 422.
  - El backend registra en el log qué respondió culqi-python en cada caso que no es éxito.
- **Compatible.** El front ya trata los errores de `/pay`; puede mostrar `detail.message`.
- **Apps:** Clientes (web y app).

## C-24 · Saldo por diferencia de peso (feature 0003, 2026-10-12) ⚠️

- **Endpoints:** `GET /pets`, `GET /pets/{id}`, `POST /pets/{id}/records`, `GET /orders/my-assignments`,
  `POST /orders/{id}/create-adjustment`, `GET /orders/pending-balance` (nuevo), `POST /holds`,
  `POST /orders`, `OrderOut` en general.
- **Qué cambia:**
  - La orden guarda el peso con que se cotizó (`declared_weight_kg` en `OrderOut`; viene de
    `meta.pet_weight_kg` del servicio base).
  - `GET /orders/my-assignments`: `pet.weight_kg` es el **peso declarado** al comprar, no el actual.
  - `PetOut.weight_locked`: `true` mientras la mascota tenga un servicio solicitado (pagado o en
    verificación, sin terminar ni cancelar). Con `true`, el dueño recibe **409 `PET_WEIGHT_LOCKED`** al
    registrar peso.
  - Cuando el groomer (o un admin) registra el peso en el servicio, la orden guarda
    `measured_weight_kg`, `measured_weight_at` y, si el precio sube, `extra_charge`. Se avisa al
    cliente (`weight_difference`) y a los admins. Si el precio baja o queda igual, no hay devolución.
  - `POST /orders/{id}/create-adjustment`: **solo admin** (antes también el groomer). Cobra
    `extra_charge`, una sola vez por orden (**409 `ADJUSTMENT_EXISTS`**; **409 `NO_EXTRA_CHARGE`** si
    no hay monto). El body se ignora. La orden queda con `adjustment_order_id`.
  - `GET /orders/pending-balance` → `{amount, currency, orders}`: órdenes de ajuste sin pagar. Se paga
    cada una con `POST /orders/{id}/pay` (tarjeta guardada, nueva o Yape).
  - Con saldo pendiente, `POST /holds` y `POST /orders` responden **409 `PENDING_BALANCE`**
    (`amount`, `currency`, `order_ids`).
- **Rompe** a la app Groomer si llamaba a `create-adjustment` (ahora 403).
- **Qué debe hacer el front:** ver `docs/guia-groomer-saldo-por-peso.md` (app Groomer). Web y admin se
  adaptan en la misma feature.
- **Apps:** Clientes, Groomer, Admin.

## C-25 · Precios por tipo de pelaje y tabla de precios del admin (feature 0004, 2026-10-13)

- **Qué cambia en la cotización** (`POST /store/quote`, catálogo con `pet_id`, carrito, saldo por peso):
  la categoría de precio vuelve a ser el **tipo de pelaje** de la raza del catálogo (`simple_short`,
  `simple_medium_long`, `curly_no_undercoat`, `double_short`, `double_long`, `mixed_curly_undercoat`).
  Mestizos, razas escritas a mano y gatos usan `mestizo`, que es también el respaldo si un producto no
  tiene precio para ese pelaje. Antes se usaba `official`/`otros`/`mestizo` y las reglas por pelaje no
  aplicaban. **Los montos que ve el cliente pueden cambiar** (ahora sí se usan las tablas por pelaje).
- **Admin:**
  - `POST /admin/store/price-rules` acepta los 6 pelajes + `mestizo` (ya no `official`/`otros`).
  - **Nuevo** `GET /admin/store/price-config`: filas (categorías con etiqueta) y tramos de peso sugeridos.
  - **Nuevo** `PUT /admin/store/price-matrix/{target_id}` `{target_type, cells:[{breed_category, weight_min, weight_max, price}], currency}`:
    reemplaza la tabla completa del producto/addon (las reglas anteriores quedan inactivas). 422 con
    `PRICE_CATEGORY_INVALID`, `PRICE_INVALID`, `WEIGHT_RANGE_INVALID`, `WEIGHT_RANGE_OVERLAP`.
  - **Nuevo** `GET /admin/store/price-simulation?category_id=&weight=&species=&breed_id=&breed_name=`:
    precio de cada producto y addon para esa mascota, la categoría usada y si se usó el respaldo.
- **Compatible** para las apps (no cambian contratos). Sin migraciones.
- **Apps:** Admin. Spec: `specs/features/0004-precios-por-pelaje/`.

## C-26 · Requisitos del servicio (peso y edad) y ocultar lo que no aplica (feature 0005, 2026-10-14)

- **Admin:** `POST /admin/store/products` y `PATCH /admin/store/products/{id}` aceptan
  `max_weight_kg` (kg) y `max_age_months` (meses); `null` = sin límite. En el PATCH, enviar `null`
  quita el límite y omitir el campo lo deja igual. `ProductOut` los devuelve en todos los endpoints.
- **Reservar** (`POST /store/quote`, carrito): si la mascota no cumple, 422 con
  `detail: {code, message}`:
  - `PET_TOO_HEAVY`: pesa más del máximo.
  - `PET_TOO_OLD`: tiene más meses del máximo.
  - `PET_AGE_UNKNOWN`: el servicio tiene edad máxima y la mascota no tiene `birth_date`.
  Mostrar `detail.message` (ya viene en español para el cliente).
- **Con `pet_id`**, `GET /store/categories/{slug}/products` ya no devuelve los servicios que la mascota
  no puede reservar (requisitos o sin precio para su pelaje/peso) y `GET /store/products/{id}` ya no
  devuelve en `available_addons` los adicionales sin precio para ella. Sin `pet_id`, todo igual.
- `GET /admin/store/price-simulation` omite los servicios que superan el peso máximo.
- **Razas:** Pug pasa a doble manto corto y Pekinés a doble manto largo (su precio cambia); nuevas
  `lagotto_romagnolo`, `perro_agua_portugues`, `aussiedoodle`.
- **Migración:** `6f7a8b9c0d1e` (columnas en `store_products` + razas). **Compatible** para las apps.
- **Apps:** Admin (campos del producto), app de clientes (mensaje del 422). Spec:
  `specs/features/0005-requisitos-servicio/`.

## C-27 · Pelaje administrable, mestizos por foto, variantes y reglas de peso (feature 0006, 2026-10-14)

- **Precio por pelaje desde la base de datos:** la categoría de precio es el `coat_type` de la raza en
  `breeds`, que ahora edita el admin. Antes estaba fijo en código. Sin pelaje → fila `mestizo`.
- **Razas** (`GET /catalog/breeds`, `GET /admin/breeds`): cada raza trae `is_mixed`, `photo_url`,
  `description`. Nuevas: `dog_mixed_1`…`dog_mixed_6` (un mestizo por pelaje, `is_mixed: true`, para elegir
  por foto), variantes `dachshund_largo`, `chihuahua_largo`, `pastor_aleman_largo`, `chow_chow_largo`,
  `cocker_spaniel_largo`, y `lagotto_romagnolo`, `perro_agua_portugues`, `aussiedoodle`. `dog_mixed`
  ("Mestizo") queda **inactivo**: ya no aparece en el catálogo público (las mascotas que lo tienen siguen
  igual). Cambian de pelaje: Pug, Pekinés y Cocker Spaniel (ahora "corte corto").
- **Admin:** `POST /admin/breeds` y `PATCH /admin/breeds/{id}` aceptan `coat_type` (uno de los 6 o null),
  `is_mixed`, `photo_url`, `description`; `coat_group` se deriva. En el PATCH solo cambia lo enviado (null
  quita). `name` ya es opcional en el PATCH. 422 `COAT_TYPE_INVALID`.
- **Fotos de razas:** `POST /media/signed-upload` acepta `entity_type: "catalog"` (solo admin; `entity_id`
  cualquier UUID). Subir con el `upload_url` y guardar el `object_name` en `photo_url` de la raza
  (`PATCH /admin/breeds/{id}`); también se acepta una URL `https://`. Las respuestas devuelven la URL
  firmada. 422 `PHOTO_URL_INVALID` si no es ni una ni otra.
- **Peso:** `POST /pets/{id}/records` (weight_record) del dueño → 409 `PET_WEIGHT_COOLDOWN` si lo cambió hace
  menos de 30 días (`detail.message` con la fecha, `detail.available_at`). El peso del registro inicial no
  cuenta. Groomer/admin sin límite. `PetOut` agrega `weight_updated_at` y `weight_editable_from` (null =
  puede cambiarlo).
- **Perfil:** `PetOut` y `PATCH /pets/{id}/optional` agregan `reactive`, `bite_history`, `muzzle_required`,
  `fragrance` (bool, opcionales).
- **Migración:** `6f7a8b9c0d1e` (la misma de C-26). Setting opcional `PET_WEIGHT_CHANGE_COOLDOWN_DAYS` (30).
- **Compatible** para las apps. **Apps:** Admin (razas), app de clientes (mestizos, peso, perfil), app de
  groomers (alertas). Spec: `specs/features/0006-razas-mestizos-peso/`.

## C-28 · Cupo diario compartido por categoría (2026-10-14)

- El cupo de un día es **uno para toda la categoría** (p. ej. 10 para PAKU Spa), no uno por servicio.
  Internamente se guarda en el servicio más antiguo de la categoría (el "ancla"); cualquier reserva de
  cualquier servicio de la categoría descuenta de él y cancelarla lo devuelve.
- Contratos iguales. `GET /availability?service_id=X` y `GET /admin/availability?service_id=X` devuelven el cupo
  compartido de la categoría de X; `service_name` ahora es "<categoría> · todos los servicios". Sin
  `service_id`, el admin solo ve los cupos compartidos. `POST /admin/availability(/bulk)` con cualquier servicio
  crea el cupo de su categoría. `GET /admin/availability/{id}/holds` lista las reservas de todos sus servicios.
- **Sin migración.** Los cupos que ya existían en otros servicios dejan de usarse.
- **Actualización (mismo C-28):** el cupo es **del día**, sin servicio:
  - `POST /admin/availability` y `POST /admin/availability/bulk`: `service_id` **opcional**; sin él se usa el
    cupo de la tienda (primera categoría activa con servicios, hoy PAKU Spa). El bulk acepta `weekdays`
    (0 = lunes … 6 = domingo; vacío = todos). 422 `WEEKDAYS_INVALID`.
  - **Nuevo** `PATCH /admin/availability/bulk` `{date_from, date_to, weekdays?, capacity?, is_active?}`: cambia cupos
    y/o abre/cierra los días ya creados del rango. Responde `{updated, below_booked}` (días donde no se bajó la
    capacidad porque hay más reservas). 422 `NOTHING_TO_UPDATE`, `DATE_RANGE_INVALID`.
  - `GET /admin/availability/{id}/holds`: cada reserva trae `service_name`.

## C-29 · Recomendaciones (documento V2), fotos previas, revisión del admin y sin cobro por peso (feature 0008, 2026-10-15)

- **Nuevo** `POST /store/recommendations` `{pet_id, product_id?, answers?}` →
  `{version, segment, service, questions, addons, review}`:
  - `service`: `{product_id, code, name, rule_id, text}` o null. Mostrar badge "Recomendado" con `text`; el
    cliente puede elegir cualquier servicio.
  - `questions`: `[{id, text, required, options:[{code,label}]}]` (Q-SHEDDING, Q-MATTING, Q-STYLING,
    Q-TOOTHBRUSH) según pelaje y, con `product_id`, solo las que disparan algo en ese servicio.
  - `addons` (con `product_id`): `[{addon_id, code, name, price, action, rule_id, text, requires_photo}]`.
    `action`: `RECOMENDAR` | `OFRECER` | null (disponible). Los no disponibles no vienen.
  - `review`: `{rule_id, text, requires_photo}` si las respuestas exigen revisión previa (manto muy apelmazado).
  - 422 `ANSWER_INVALID` (pregunta o código desconocido).
- **Carrito:** la línea `service_base` acepta `meta.answers` (`{"Q-MATTING": "LOCALIZED", …}`). El servidor guarda
  `meta.recommendation` (versión, reglas, si requiere fotos o revisión).
- **Orden** (`OrderOut`): `review_status` (`pending` | `approved` | `rejected` | null), `review_note`,
  `reviewed_at`, `requires_photos`, `recommendation`.
- **Fotos previas:** el dueño sube con `POST /media/signed-upload` (`entity_type: "order"`, `entity_id`: su orden)
  y registra con `POST /orders/{id}/photos` (se guarda como `kind: "pre_service"`). `POST /orders/{id}/pay`
  sin fotos cuando `requires_photos` → 409 `PHOTOS_REQUIRED`.
- **Admin:** `POST /admin/orders/{id}/review` `{approved, note?}` (rechazar cancela y libera el cupo; 409
  `REVIEW_NOT_PENDING`). `POST /admin/orders/{id}/assign` con revisión pendiente → 409 `REVIEW_PENDING`.
  Productos: `code`; adicionales: `code`, `requires_photo`, `duration_extra_min` (PATCH, solo lo enviado).
- **Peso:** registrar el peso en el servicio ya **no** genera cobro (`extra_charge` queda null) ni avisos;
  `price_check` viene null. Los saldos anteriores siguen como estaban.
- **Migración:** `7a8b9c0d1e2f`. **Apps:** cliente, admin, groomer. Spec: `specs/features/0008-recomendaciones-v2/`.

## C-30 · Seguridad y perfume en la ficha del groomer (2026-10-15)

- `GET /orders/my-assignments[/{id}]`: `pet` agrega `reactive`, `bite_history`, `muzzle_required` y `fragrance`
  (bool o null), para mostrar alertas en la ficha del servicio. Sin migración. **Apps:** groomer.

## C-31 · Rango de precios por tamaño (2026-10-16)

- **Nuevo** `GET /store/categories/{slug}/price-ranges?breed_id=&species=dog` (público):
  `[{weight_min, weight_max, min_price, max_price}]`, uno por tramo de peso (≤5, ≤15, ≤25, ≤35, ≤50, >50).
  Mínimo y máximo de los servicios activos sin requisitos de edad/peso, para el pelaje de la raza.
- Uso: el registro de mascota ya no pide el peso; se elige el tamaño (tramo) mostrando su rango de precio.
  Sin migración. **Apps:** cliente.

## C-32 · Tiempos de atención del groomer (2026-10-16)

- `OrderOut` agrega `departed_at` (salió hacia el domicilio) y `completed_at` (terminó el servicio). Junto con
  `service_steps_log` (inicio de cada paso) permiten calcular traslado, duración por paso y total.
- Se llenan solos al cambiar a `on_the_way` y `done`. Órdenes anteriores: null.
- **Migración:** `8b9c0d1e2f3a`. **Apps:** admin (pantalla Tiempos).

## C-33 · Precio "desde" por servicio (2026-10-27)

- `GET /store/categories/{slug}/products` agrega `min_price` en cada producto: el precio más bajo de su tabla
  (cualquier pelaje y peso). `price` sigue siendo el precio exacto para la mascota (null sin mascota).
- Uso: la web muestra "Desde S/ X" a quien no inició sesión. **Sin migración.**

## C-34 · Inventario: insumos, movimientos, recetas y costo por orden (feature 0009, 2026-10-29)

- **Nuevos (admin):** `GET /admin/inventory/config` (categorías, unidades, tipos de movimiento, ubicaciones y
  centros de costo); `GET/POST /admin/inventory/supplies` y `PATCH /admin/inventory/supplies/{id}` (el código
  `INS-001` lo da el backend; cada insumo trae `stock`, `status` `ok|low|out`, `value` y `unit_cost`);
  `GET/POST /admin/inventory/movements` (filtros `type`, `supply_id`, `order_id`, `date_from`, `date_to`, `limit`);
  `GET /admin/inventory/summary?date_from&date_to`; `GET /admin/inventory/recipes`;
  `GET/PUT /admin/inventory/recipes/{target_id}` y `GET …/{target_id}/versions`;
  `GET /admin/inventory/orders/{id}/cost`; `POST /admin/inventory/orders/{id}/consume`.
- Movimientos: `quantity` siempre positiva; el signo sale del tipo (`adjustment` exige `direction` `in|out`).
  Motivo obligatorio; no se editan ni se borran. Errores con `code`: `MOVEMENT_*`, `SUPPLY_*`, `LOCATION_INVALID`,
  `COST_CENTER_INVALID`, `RECIPE_UNCHANGED`, `RECIPE_NOT_CURRENT`, `CONSUMPTION_ALREADY_REGISTERED`, y los de la
  tabla de precios (`PRICE_CATEGORY_INVALID`, `WEIGHT_RANGE_*`).
- Recetas (2026-10-29, rehecho antes de desplegar): **misma forma que la tabla de precios** — una por servicio y
  por adicional (`target_id`), celdas `{breed_category, weight_min, weight_max, labor_minutes, lines}` con las
  filas y tramos de `GET /admin/store/price-config`. La orden usa la celda con la regla del precio (pelaje o
  "mestizo"; tramo del peso registrado). Cada celda devuelve `supplies_cost`, `labor_cost`, `total_cost`, `price`
  y `margin`. El costeo de la orden trae insumos, mano de obra estimada y real (C-37) y márgenes.
- **Cambio de comportamiento:** al pasar una orden a `done` (`/complete` o "cerrar a mano" del admin) se registran
  solos sus consumos (`type=consumption`, `created_by` null = sistema). Best effort: la orden termina igual.
- **Compatible.** **Migración:** `9c0d1e2f3a4b`. **Apps:** admin (Inventario: Insumos, Movimientos, Recetas y costeo).

## C-35 · Parámetros generales y anticipación mínima (feature 0010, 2026-10-29)

- **Nuevos (admin):** `GET /admin/settings` (`values` y `sections` con etiqueta, tipo, valor por defecto y si es
  editable) y `PATCH /admin/settings` con `{"values": {clave: valor}}` (solo lo cambiado; `null` vuelve al valor
  por defecto; todo o nada: 422 `SETTING_INVALID` con `key`).
- Solo lectura: `timezone` (America/Lima), `currency` (PEN) y `reservation_ttl_minutes` (120 = vida del carrito).
- **Cambio de comportamiento (solo si el admin lo configura):** con `booking_min_days_ahead` = N > 0,
  `GET /availability` omite los días antes de hoy + N y `POST /holds` responde 422 `DATE_TOO_SOON` con
  `earliest_date`. Por defecto 0: igual que antes.
- **Compatible.** **Migración:** `0d1e2f3a4b5c`. **Apps:** admin (Parámetros generales); app de clientes
  (mostrar `detail.message` de `DATE_TOO_SOON`).

## C-36 · Clientes: resumen por dueño (feature 0011, 2026-10-29)

- **Nuevos (admin):** `GET /admin/customers` (filtros `segment`, `district_id`, `q`, `last_visit_from`,
  `last_visit_to`; `sort` `spend|last_visit|services`), `GET /admin/customers/stats` (totales y segmentos con su
  regla) y `GET /admin/customers/{user_id}` (ficha con `pets_detail` y `visits`).
- Servicio = orden terminada sin orden padre; `spend` = lo pagado (orden + cargos extra pagados). Segmentos:
  `vip`, `recurrente`, `nuevo`, `sin_recompra`, `en_riesgo`, `inactivo`.
- Resuelve el pedido del admin de "un endpoint de resumen por cliente" para no traer todas las órdenes.
- **Compatible.** **Sin migración.** **Apps:** admin (CRM · Clientes).

## C-37 · Costo del groomer y mano de obra (feature 0012, 2026-10-29)

- **Nuevos (admin):** `GET /admin/groomer-costs` (cada groomer con su registro vigente, `reference_rate` y cargos
  sugeridos), `GET /admin/groomer-costs/{groomer_id}` (historial) y `POST /admin/groomer-costs/{groomer_id}`
  (`effective_from`, `base_salary`, `items` `[{label, kind: percent|amount, value}]`, `monthly_hours`,
  `driving_rest_hours`; misma fecha = corrige).
- Devuelve `monthly_cost`, `service_hours` y `cost_per_service_hour` (costo mensual ÷ horas de servicio): la tarifa
  de las recetas y del costeo.
- **Compatible.** **Migración:** `1e2f3a4b5c6d`. **Apps:** admin (Groomers, Recetas y costeo).

## C-38 · Campañas y descuentos (feature 0013, 2026-10-29)

- **Nuevos (admin):** `GET /admin/campaigns/config`, `GET/POST /admin/campaigns`, `PATCH /admin/campaigns/{id}`
  (editar, activar, pausar o terminar con `status`). Cada campaña trae `state`, usos, `discount_given`, `sales` y
  `audience_size`.
- **Nuevo (cliente):** `POST /campaigns/quote` `{cart_id, code?}` → `subtotal`, `discount`, `total` y la campaña.
- **Cambio en `POST /orders`:** acepta `campaign_code` (opcional). Se aplica la mejor campaña (automáticas del
  cliente + el cupón). Cupón inválido → 422 con `code` `CAMPAIGN_*` y no se crea la orden. `OrderOut` agrega
  `discount_amount` y `campaign_id`; **`total_snapshot` pasa a ser el neto** (lo que cobra Culqi). Cancelar libera
  el uso.
- **Compatible** (campos nuevos opcionales), pero los fronts que suman los ítems para mostrar el total deben usar
  `total_snapshot` (o mostrar `discount_amount`). **Migración:** `2f3a4b5c6d7e`. **Apps:** admin (CRM · Campañas,
  Órdenes), app de clientes (cupón y total).

## C-39 · Dashboard gerencial (feature 0014, 2026-10-29)

- **Nuevo (admin):** `GET /admin/dashboard?date=YYYY-MM-DD` (corte; hoy en Lima por defecto). Devuelve `period`
  (del 1 al corte), `previous_period` (mismo corte del mes anterior), `metrics`, `scheduled_rest_of_month` y
  `next_days` (7 días desde el corte: `capacity`, `booked`, `occupancy_pct`, `scheduled`).
- Cada métrica: `key`, `label`, `unit` (`count|money|pct|minutes`), `description` (cómo se calcula), `value`,
  `previous`, `delta`, `delta_pct`, `quality` y `previous_quality` (`real|estimated|no_data`; con `no_data` el
  valor es null, nunca 0) y, en las parciales, `with_data` de `total` órdenes.
- Métricas: servicios realizados, ingresos, ticket promedio, por cobrar, cancelaciones, ocupación, clientes nuevos y
  con recompra, contribución estimada y su margen, traslado, atención, llegada vs. hora programada y avisos de
  retraso. Reglas en `specs/features/0014-dashboard-gerencial/spec.md`.
- **Compatible.** **Sin migración.** **Apps:** admin (Resumen gerencial).

## C-40 · Capturas del inventario (feature 0015, 2026-11-01)

- **Nuevos (admin):** `GET /admin/inventory/snapshots?date_from&date_to` → `{schedule: {frequency, frequency_label,
  next_cut}, items}`; `GET /admin/inventory/snapshots/{id}` (con `lines`: stock, mínimo, costo, valor y estado de cada
  insumo al corte; 404 `SNAPSHOT_NOT_FOUND`); `POST /admin/inventory/snapshots` (captura manual con corte hoy).
- **Automática:** al terminar el día de corte (hora de Lima) según `inventory_snapshot_frequency` en
  `/admin/settings`: `weekly` (domingo), `semimonthly` (15 y fin de mes), `monthly` (fin de mes, por defecto) o
  `none`. Una por corte; si el servidor estuvo apagado, se recupera hasta 3 días después.
- **`/admin/settings`:** nuevo tipo de campo `choice` con `options` `[{value, label}]` y sección `inventory`.
- **Compatible.** **Migración:** `3a4b5c6d7e8f`. **Apps:** admin (Inventario · Capturas, Parámetros).

## C-41 · Reporte de ventas (feature 0016, 2026-11-01)

- **Nuevo (admin):** `GET /admin/reports/sales` con `date_from`, `date_to`, `date_basis` (`purchase` = fecha de
  compra, por defecto | `service` = fecha del servicio), `order_status`, `payment_status`, `payment_method`,
  `service_id`, `groomer_id`, `district_id`, `campaign_id` y `q` (cliente, mascota o n.º de orden).
- Devuelve `rows` (una por orden de servicio: cliente, mascota, servicio y adicionales, `subtotal`, `discount`,
  `total` neto, `extra_paid`, `collected`, pago, estado, groomer, distrito y campaña), `totals`, `by_service`,
  `by_payment_method`, `by_order_status` y `options` para los filtros. 422 `DATE_BASIS_INVALID` / `DATE_RANGE_INVALID`.
- **Compatible.** **Sin migración.** **Apps:** admin (Reporte de ventas).

## C-42 · Resultados de las campañas (feature 0017, 2026-11-01)

- **Nuevo (admin):** `GET /admin/campaigns/results` → `{items: [{campaign_id, code, name, state, starts_on, ends_on,
  result}], total}`. `result`: `sold` (pagadas y no canceladas), `done`, `customers`, `new_customers`, `subtotal`,
  `discount`, `discount_pct`, `net`, `extra_paid`, `collected`, `costed`, `cost`, `margin`, `margin_pct` (los tres
  últimos null si ninguna realizada se pudo costear). Campañas sin ventas en cero. Reglas en
  `specs/features/0017-resultados-campanas/spec.md`.
- **Compatible.** **Sin migración.** **Apps:** admin (CRM · Campañas, Reporte de ventas con `?campaign_id=`).

## C-43 · Clientes atendidos por mes (feature 0011, 2026-11-02)

- **`GET /admin/customers/stats`** agrega `by_month`: el mes en curso (al día, hora de Lima) y los 5 anteriores, del
  más antiguo al actual, con `month` (`YYYY-MM`), `attended` (clientes con al menos un servicio terminado ese mes),
  `new` (su primer servicio cae en ese mes) y `returning` (atendidos cuyo primer servicio fue antes). Mismas
  definiciones que el dashboard.
- **Compatible** (campo nuevo). **Sin migración.** **Apps:** admin (CRM · Fidelización, ahora real).

## C-44 · Integración de correo: configuración de Resend (feature 0018 fase 1, 2026-11-02)

- **Nuevos (admin):** `GET /admin/integrations/email` → `{provider, providers, enabled, configured, api_key_mask
  (p. ej. "re_12…9aXz", nunca la key completa), from_email, from_name, reply_to, status (not_configured | disabled |
  active | error), last_test_at, last_test_ok, last_test_error, encryption_ready, updated_at, updated_by}`.
- `PUT /admin/integrations/email` con `{provider, enabled, api_key?, from_email, from_name, reply_to}`: `api_key` vacía
  o ausente conserva la guardada. 422 `EMAIL_CONFIG_INVALID` con `field` (no guarda nada); 503
  `ENCRYPTION_UNAVAILABLE` si el servidor no tiene la llave.
- `POST /admin/integrations/email/test` con `{to?}` (por defecto el correo del admin) → `{ok, to,
  provider_message_id, error}`; si Resend rechaza responde 200 con `ok: false`. 409 `EMAIL_NOT_CONFIGURED`.
- **Servidor:** nueva variable `CREDENTIALS_ENCRYPTION_KEY` (llave Fernet; generar con
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`). Guardarla: si se
  pierde, hay que volver a ingresar la API key. Nueva dependencia `cryptography` en `requirements.txt`.
- **Compatible.** **Migración:** `4b5c6d7e8f9a` (`channel_providers`). **Apps:** admin (Configuración · Integraciones).

## C-45 · Registro de envíos y reintentos (feature 0018 fase 2, 2026-11-02)

- **Nuevos (admin):** `GET /admin/notification-logs?channel&status&q&date_from&date_to&limit&offset` → `{items, total,
  counts}`. Cada envío: `recipient`, `template`, `subject`, `status` (`PENDING` | `SENT` | `FAILED`),
  `provider_message_id`, `error`, `retryable` + `next_attempt_at` (se reintentará solo), `attempts`, `user_id`,
  `order_id`, `campaign_id`, `created_at`, `sent_at`. Más recientes primero; fechas = día de creación en Lima;
  `counts` por estado ignora el filtro de estado. 422 `LOG_STATUS_INVALID` / `DATE_RANGE_INVALID`.
- `POST /admin/notification-logs/{id}/retry`: reintenta ahora un `FAILED`. 404 `LOG_NOT_FOUND`, 409 `LOG_NOT_RETRYABLE`.
- **Backend:** `send_email(session, to, subject, html, text, idempotency_key, template, user_id, order_id,
  campaign_id)` en `app/modules/messaging/app/sender.py`. La misma `idempotency_key` no sale dos veces (también va a
  Resend en `Idempotency-Key`). Fallas temporales (429, 5xx, sin conexión) se reintentan solas a 1, 5, 15 y 60 min,
  hasta 5 intentos (job cada minuto); un `PENDING` colgado más de 10 min también se reintenta. Correo sin configurar o
  desactivado → `FAILED` sin reintento.
- `POST /admin/integrations/email/test` ahora también queda en el registro (`template: "test"`, sin reintento solo).
- **Compatible.** **Migración:** `5c6d7e8f9a0b` (`notification_logs`). **Apps:** admin (Configuración · Integraciones).

## C-46 · Simulador de un servicio (feature 0019, 2026-11-02)

- **Nuevo (admin):** `POST /admin/inventory/simulate` con `{product_id, addon_ids, breed_id?, weight_kg, groomer_id?}`.
  No registra nada. Sin raza se usa la fila «mestizo»; la celda de cada receta y el precio se eligen igual que en una
  orden real; mano de obra con el costo por hora del groomer elegido o el de referencia.
- Devuelve `breed_category` (+ `_label`), `weight_code`, `items` (servicio y cada adicional: `price`,
  `recipe_version`, `category_used`, tramo, `labor_minutes`, `supplies_cost`, `lines`), `supplies` (consumo total por
  insumo con `cost_share_pct`, `stock` de hoy, `stock_status` y `services_with_stock`), `price`, `supplies_cost`,
  `labor_minutes`, `labor_rate` + `labor_rate_source`, `labor_cost`, `total_cost`, `margin`, `margin_pct`,
  `max_services_with_stock` y `warnings` (sin receta, sin precio, sin tarifa, peso sobre el máximo, inactivo).
- 404 `PRODUCT_NOT_FOUND` / `ADDON_NOT_FOUND` / `BREED_NOT_FOUND`; 422 `ADDON_NOT_IN_SERVICE` / `WEIGHT_INVALID`.
- **Compatible.** **Sin migración.** **Apps:** admin (Inventario · Recetas y costeo · Simulador de servicio).

## C-47 · Nubefact: conexión para boletas (feature 0020 fase 1, 2026-11-02)

- **Nuevos (admin):** `GET /admin/integrations/nubefact` → `{enabled, configured, api_url, token_mask (nunca el token
  completo), boleta_series, status (not_configured | disabled | active | error), last_test_at, last_test_ok,
  last_test_error, encryption_ready, updated_at, updated_by, readiness}`. `readiness`: `company_ruc`, `company_name`,
  `igv_percent` (Parámetros generales), `customers` y `customers_with_dni` (clientes activos y con DNI).
- `PUT /admin/integrations/nubefact` con `{enabled, api_url, token?, boleta_series}`: `token` vacío conserva el
  guardado; ruta https (http solo en localhost, versión offline); serie de 4 caracteres que empieza con B (por
  defecto B001). 422 `INVOICING_CONFIG_INVALID` con `field`; 503 `ENCRYPTION_UNAVAILABLE`.
- `POST /admin/integrations/nubefact/test` → `{ok, message}`: consulta la boleta `{serie}-99999999`; **no emite
  nada**. «No existe» (código 24) = conexión correcta. 409 `INVOICING_NOT_CONFIGURED`.
- Todavía no se emiten comprobantes (decisiones pendientes en `specs/features/0020-boletas-nubefact/spec.md`).
- **Compatible.** **Migración:** `6d7e8f9a0b1c` (`invoicing_providers`). Usa `CREDENTIALS_ENCRYPTION_KEY` (C-44).
  **Apps:** admin (Configuración · Integraciones).

## C-48 · Inventario: ficha del insumo, precio en la compra y anulación (feature 0021, 2026-11-09)

- **Insumos** (`GET/POST/PATCH /admin/inventory/supplies`): nuevos `brand`, `description` (opcionales; vacío = sin
  dato) y `suppliers: [{name, phone, address, bank_account, ruc}]` (solo `name` obligatorio; `ruc` de 11 dígitos).
  En `PATCH`, `suppliers` reemplaza la lista completa. 422 `SUPPLIER_NAME_REQUIRED` / `SUPPLIER_RUC_INVALID` con
  `index`. `GET /admin/inventory/config` → `consumption_units` incluye `L`.
- **Registrar movimiento** (`POST /admin/inventory/movements`): `quantity` pasa a opcional; se envía `quantity`
  (unidad de consumo) **o** `purchase_quantity` (unidades de compra, solo `purchase` / `initial_stock`).
  `purchase_price` (S/ por unidad de compra) es **obligatorio en `purchase`** y opcional en `initial_stock`; el
  movimiento queda a ese precio y el costo del insumo pasa al promedio ponderado. 422 `MOVEMENT_PRICE_REQUIRED` /
  `MOVEMENT_PRICE_NOT_ALLOWED` / `MOVEMENT_PRICE_INVALID` / `MOVEMENT_QUANTITY_INVALID`.
- **Nuevo:** `POST /admin/inventory/movements/{id}/void` con `{reason}` → el movimiento con `voided_at`. Deja de
  contar en stock, valor y consumo; no se borra. 404 `MOVEMENT_NOT_FOUND`; 409 `MOVEMENT_ALREADY_VOIDED` /
  `MOVEMENT_NOT_VOIDABLE` (consumo por receta de una orden); 422 `VOID_REASON_REQUIRED`.
- `GET /admin/inventory/movements`: sin los anulados salvo `include_voided=true`. `MovementOut` suma
  `purchase_quantity`, `purchase_price`, `voided_at`, `voided_by`, `voided_by_name`, `void_reason` y `can_void`.
- **Rompe** solo para quien registre compras sin `purchase_price` (el admin ya lo envía). **Migración:**
  `7e8f9a0b1c2d`. **Apps:** admin (Inventario · Insumos y Movimientos).

## C-49 · Código del producto del proveedor y margen sin IGV en recetas (feature 0021, 2026-11-09)

- `suppliers[]` de un insumo suma `product_code` (opcional, máx. 60): el código con que el proveedor conoce el
  producto.
- Recetas (`GET /admin/inventory/recipes/{id}`, `/versions`, `PUT`): cada celda suma `price_without_igv`
  (= `price` ÷ (1 + IGV)) y `margin` pasa a ser **precio sin IGV − costo total** (antes: precio − costo). `RecipeOut`
  suma `igv_percent` (de Parámetros generales). Solo recetas: simulador, costo de orden y campañas no cambian.
- **Compatible** (mismo campo `margin`, valor nuevo). **Sin migración.** **Apps:** admin (Insumos, Recetas y costeo).

## C-50 · Inventario: compra con cantidad real y total pagado; editar movimientos (feature 0021, 2026-11-09)

- **Registrar movimiento** (`POST /admin/inventory/movements`): `quantity` vuelve a ser **obligatoria** y siempre en
  unidad de consumo (100 L). Se quitan `purchase_quantity` y `purchase_price` (C-48); ahora va `purchase_total`
  (S/ pagado por la entrada): obligatorio en `purchase`, opcional en `initial_stock`. Costo por unidad = total ÷
  cantidad; el costo del insumo pasa al promedio ponderado. `MovementOut`: `purchase_total` en lugar de
  `purchase_quantity` / `purchase_price`.
- **Nuevo:** `PATCH /admin/inventory/movements/{id}` con `edit_reason` (obligatorio) y solo lo que cambia:
  `occurred_on`, `supply_id`, `quantity`, `purchase_total` (null lo quita; en compra es obligatorio), `direction`
  (ajustes), `reason`, `location`, `cost_center`, `lot`, `expires_on`. El tipo no se edita. El costo promedio del
  insumo no se recalcula. 404 `MOVEMENT_NOT_FOUND` / `SUPPLY_NOT_FOUND`; 409 `MOVEMENT_NOT_EDITABLE` (anulado o
  consumo por receta) / `MOVEMENT_UNCHANGED` / `SUPPLY_INACTIVE`; 422 `EDIT_REASON_REQUIRED` y las reglas del registro.
- **Nuevo:** `GET /admin/inventory/movements/{id}/edits` → `[{id, edited_at, edited_by, edited_by_name, reason,
  changes: {campo: {before, after}}}]`, la más reciente primero.
- `MovementOut` suma `can_edit`, `edited_at` y `edited_by_name`.
- **Rompe** C-48 (no desplegado): quien envíe `purchase_quantity` / `purchase_price` debe enviar `quantity` y
  `purchase_total`. **Migración:** `8f9a0b1c2d3e` (backfill del total en las entradas con precio). **Apps:** admin.

## C-51 · Inventario: anular o editar una entrada recalcula el costo promedio (feature 0021, 2026-11-09)

- `POST /admin/inventory/movements/{id}/void` y `PATCH /admin/inventory/movements/{id}`: si el movimiento es (o pasa
  a ser) una entrada, el `purchase_cost` del insumo se recalcula repasando sus movimientos vigentes en orden; si
  cambia el insumo, se recalculan los dos. Misma transacción que la anulación o la edición. Sin entradas vigentes la
  ficha no cambia. Antes (C-48 / C-50) el promedio no se recalculaba.
- **Compatible** (mismas rutas y respuestas). **Sin migración.** **Apps:** admin (recargar Insumos para ver el costo).
## C-52 · Libro de Reclamaciones virtual (feature 0022, 2026-11-09)

- **Nuevo (público, sin sesión):** `POST /complaints` con `consumer_name`, `doc_type` (`dni|ce|pasaporte|ruc`),
  `doc_number`, `email`, `phone?`, `address?`, `is_minor`, `guardian_name?` (obligatorio si `is_minor`),
  `item_type` (`servicio|producto`), `item_description`, `order_reference?`, `amount_claimed?`, `kind`
  (`reclamo|queja`), `detail`, `request` → 201 `{id, code, created_at, response_due, email, provider_legal_name,
  provider_ruc, provider_address}`. 422 `COMPLAINT_INVALID` con `field`; 429 `TOO_MANY_ATTEMPTS`. Envía la copia al
  consumidor y un aviso al correo de reclamos.
- **Nuevo (admin):** `GET /admin/complaints?status=received|answered&limit&offset` → `{items, total}` (cada ítem con
  `code`, `kind_label`, `status_label`, `response_due`, `overdue`); `GET /admin/complaints/{id}` (suma `sheet:
  [{label, value}]`, `response`, `responded_at`); `POST /admin/complaints/{id}/answer` `{response}` → 404
  `COMPLAINT_NOT_FOUND`, 409 `COMPLAINT_ALREADY_ANSWERED`, 422 `COMPLAINT_INVALID`.
- **Parámetros generales:** nuevos `company_legal_name`, `company_address`, `complaints_email`; `company_ruc` tiene
  valor por defecto.
- **Compatible.** **Migración:** `9a0b1c2d3e4f`. **Apps:** web (Libro de Reclamaciones) y admin.

## C-53 · Adicionales incompatibles y adicionales no disponibles en el carrito (2026-11-13)

- `POST /store/quote` y el carrito rechazan con 422 `ADDONS_INCOMPATIBLE` (`message`, `addon_codes`) las
  combinaciones que son alternativas o repiten trabajo: Corte estético + Rapado corporal (`ADD_CORTE_EST` /
  `ADD_CORTE_CORTO`), Desmotado localizado + extendido, Retoque de carita + Retoque Paku (`ADD_CARITA` /
  `ADD_RETOQUE`), y Corte estético + cualquiera de los dos retoques. Reglas en `store/domain/addon_conflicts.py`.
- El carrito rechaza con 422 `ADDON_NOT_AVAILABLE` (`addon_code`) un adicional que las reglas de recomendación
  marcan `NO_DISPONIBLE` para la mascota (antes solo se ocultaba en `/store/recommendations` y se podía elegir a mano).
- `AddonOut` (detalle del servicio y admin) y los adicionales de `/store/recommendations` suman
  `incompatible_with: [códigos]` para que la web y la app deshabiliten la opción incompatible.
- **Compatible.** **Sin migración.** Los adicionales sin código no participan: en Fresco y Limpio hay que asignar
  `ADD_CORTE_EST` a «Corte estético» y `ADD_CARITA` a «Retoque de carita» (admin → Tienda).
