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
