# Plan de trabajo — paku-backend

Creado: 2026-10-03. Fuente de verdad del trabajo en curso. Se actualiza al cerrar cada tarea.

## Reglas de trabajo

- El backend **ya está consumido** por 3 fronts (app clientes, app Paku Groomer, web admin).
  Todo cambio que toque la API se registra en [`cambios-api-para-front.md`](cambios-api-para-front.md)
  en el mismo momento en que se hace.
- **Sin base de datos ahora.** La BD se conecta al desplegar. Las migraciones Alembic se escriben
  pero **no se ejecutan**. Se verifica con tests unitarios (sin BD).
- Los commits los hace el dueño del repo.
- Solo se pregunta al dueño cuando es una **decisión de negocio**. Lo técnico se decide y se documenta.
- No se agrega lógica nueva a `pet_records` (el historial se mudará a HCVet, etapa 2).
- El backend calcula, el front muestra: todo monto sale del servidor y se devuelve en las respuestas.

## Decisiones del dueño (2026-10-03)

| # | Decisión |
|---|---|
| 1 | El precio lo calcula el backend con `store` (misma lógica que `POST /store/quote`). El `unit_price` del front se acepta y se ignora; la respuesta trae el precio del servidor. |
| 2 | Formato único de addons: cada addon es una línea `kind=service_addon`, `ref_id=<addon_id>`. Un addon solo existe como complemento del servicio base del carrito y se valida y cotiza por especie, raza y peso. |
| 3 | Cambios de estado de órdenes: solo admin o groomer asignado. El cliente no. |
| 4 | El groomer puede generar un cargo extra cuando el peso real supera al declarado. |
| 5 | Booking por día con cupos configurables. Las reservas que expiran liberan cupo. Nadie confirma ni cancela reservas ajenas. |
| 6 | "ally" se reemplaza por "groomer" en todo, de una vez; los fronts actualizan en el mismo despliegue. |
| 7 | Pagos/Culqi, refresh token y streaming quedan para el final (documentados como pendientes). |
| 8 | HCVet (historia clínica) es etapa 2. Baño y grooming serán eventos de HCVet. Todo dueño de Paku llega a HCVet con DNI. Paku entra a HCVet como un centro veterinario más, con su API Key. |

## Supuestos técnicos tomados sin preguntar (revisables)

- ~~`PATCH /orders/{id}`~~: el front confirmó que nadie lo usa → eliminado (C-16, 2026-10-05).
- Ítems de carrito `kind=product`: se rechazan; el front confirmó que ninguna app los envía (2026-10-05).
- Si el precio cambió entre "agregar" y "checkout", el checkout responde 409 `PRICE_CHANGED` con precios anteriores y nuevos.
- Compatibilidad del renombre: un token con `role: "ally"` se trata como `groomer` hasta que expire.
- Una orden `skipped` se puede cancelar desde admin (además de reprogramarla). Al reprogramar se
  conservan `skip_reason`/`skip_note`/`skipped_at` como historial.
- `/complete` permite cerrar órdenes que ya estaban en servicio antes del despliegue (sin `service_step`).
- Pesaje de recepción: no se guarda en la orden (el pedido del front prohíbe entidades extra); sigue el
  flujo actual de registro de peso + cargo extra.

---

## Etapa 1 — Paku

### Fase 0 — Documentos
- [x] 0.1 `docs/cambios-api-para-front.md` (changelog para los fronts)
- [x] 0.2 `docs/consultas-para-front.md` (preguntas al front)
- [x] 0.3 `docs/pendientes.md` (por decidir / para después)
- [x] 0.4 `docs/pendientes-pagos-culqi.md`
- [x] 0.5 Actualizar `specs/constitution.md` y `specs/workspace.md` (groomers de Paku, modelo van, apps, regla "backend calcula, front muestra")

### Fase 1 — Correcciones
- [x] 1.1 Bug: `status` tapa al módulo `fastapi.status` en `PatchOrder` / `UpdateOrderStatus` (500 en vez de 400/404/409) — C-01
- [x] 1.2 Autenticación y propiedad: `GET /pets/{id}` (dueño, groomer asignado, admin) — pedido 1 del front; endpoints de `store` con `?pet_id=` solo para el dueño o admin — C-04, C-05
- [x] 1.3 Cambios de estado de órdenes solo admin o groomer asignado (`PATCH /orders/{id}`, `POST /orders/{id}/status`) — C-02
- [x] 1.4 Cargo extra por peso: solo groomer asignado a esa orden o admin — C-03
- [x] 1.5 (C-07, C-08) Precios desde el servidor: carrito (agregar, lote, reemplazar), checkout con `PRICE_CHANGED`, nombre desde `store`, formato único de addons, validación de especie / razas permitidas / servicio base; listado de servicios filtrado por raza permitida
- [x] 1.6 Booking: expiración libera cupo; cancelar guarda la liberación; solo dueño o admin confirma/cancela — C-06

### Fase 2 — Renombre ally → groomer
- [x] 2.1 Código, API, notificaciones y docs: `ally_id`→`groomer_id`, `?ally_id=`→`?groomer_id=`, `ally_location`→`groomer_location`, rol `ally`→`groomer` (chat, historial) — C-09
- [x] 2.2 Migración Alembic `1a2b3c4d5e6f` (no ejecutada): rol en `users`, `chat_messages.sender_role`, `pet_records.recorded_by_role`, columnas `ally_id` de `orders` y `order_assignments`, tabla `ally_locations` → `groomer_locations`
- [x] 2.3 Compatibilidad: token con rol `ally` = `groomer` (`normalize_role` en `app/core/auth.py`)

### Fase 3 — Pedidos del front (`docs/pedidos-al-backend.md`)
- [x] 3.1 Pedido 2: `GET /orders/my-assignments?date=` (America/Lima), `GET /orders/my-assignments/{id}`, datos de mascota, cliente y servicio — C-10
- [x] 3.2 (C-11, migración `2b3c4d5e6f7a`) Pedido 3: `service_step` + `POST /orders/{id}/next-step`, `addons_done` + `POST /orders/{id}/addons/{addon_id}/done`, `/complete` exige `return`, texto de notificación de llegada (+ migración). Sin "pesaje en la orden": el pedido prohíbe entidades extra; el peso sigue por registro de peso + cargo extra.
- [x] 3.3 (C-12, misma migración) Pedido 6: fotos de la orden (`entity_type="order"`, `POST/GET /orders/{id}/photos`) (+ migración)
- [x] 3.4 (C-13, migración `3c4d5e6f7a8b`) Pedido 4: estado `skipped`, `POST /orders/{id}/skip`, reasignar devuelve a `created` (+ migración)
- [x] 3.5 (C-14, misma migración) Pedido 5: `POST/GET /orders/{id}/delay-reports` (+ migración)
- [x] 3.6 Pedido 7: `GOOGLE_ROUTES_API_KEY` **no está** en `.env` ni en `docker-compose.yml` (solo en `.env.example`). Configurarla en el servidor — ver `pendientes.md`.

### Fase 4 — Limpieza
- [x] 4.1 `.dockerignore` creado (no copia `.env`, `.venv`, `*.db`, tests, docs) y `.gitignore` con `*.db` y `cloud-sql-proxy.exe`.
  **Lo hace el dueño (borra archivos del repo):**
  `git rm --cached app.db cloud-sql-proxy.exe` y `git rm check_districts.py show_summary.py test_districts_simple.py test_hardcoded_districts.py test_integration_geo_address.py test_social_auth.py verify_cart_schema.py verify_implementation.py`
- [x] 4.2 README sin enlaces rotos; `holds.py` duplicado resuelto en 1.6.
  **Lo hace el dueño:** `git rm -r app/modules/paku_spa` (archivos vacíos) y borrar las carpetas locales `app/modules/commerce` y `app/modules/clinical_history` (solo tienen `__pycache__`, no están en git).
- (Antes 4.2) Código muerto (~~`booking/.../holds.py` duplicado~~ hecho en 1.6, `__pycache__` de `commerce` y `clinical_history`, `paku_spa` vacío) y enlaces rotos del README

### Fase 5 — Booking ligado a la compra (2026-10-04)
- [x] 5.1 Reserva antes de comprar; dura lo que el carrito (2 h); `meta.hold_id` obligatorio en el servicio base; vence con el carrito; se confirma con la orden; se libera al cancelar/saltar — C-15
- [x] 5.2 Bugs: "hoy" en hora de Lima, fechas pasadas, mascota ajena, una reserva por mascota y día, 409/404 en vez de 500 al crear cupos, capacidad no menor a lo reservado
- [x] 5.3 `GET /holds` (cliente) y `GET /admin/availability/{slot_id}/holds` (admin)
- [ ] 5.4 **Lo hace el dueño:** `git rm app/modules/booking/infra/hold_repository.py` (repositorio en memoria sin uso)

### Al final de la etapa 1
- [ ] Pagos/Culqi (`pendientes-pagos-culqi.md`)
- [ ] Refresh token, streaming (`pendientes.md`)

## Etapa 2 — Integración con HCVet (no iniciar)

- HCVet: veterinarios/centros con API Key (su plan, pasos 2–4); tipos de evento baño y grooming; propietario con DNI obligatorio.
- Paku: pedir DNI a todos los dueños antes de integrar; Paku como centro veterinario con API Key; `/pets/{id}/records` de Paku pasa a ser intermediario hacia HCVet (los fronts no cambian); migración de registros existentes; el peso para precio se queda en Paku.
