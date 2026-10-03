PEDIDOS BACKEND — App Groomer (rol "ally") — v1 final
Contexto: 1 orden = 1 mascota = 1 parada. Modelo van: el groomer recoge a la mascota,
hace el grooming en la van y la devuelve. El admin define el orden de la ruta vía
scheduled_at (ya existe). Regla: no agregar entidades ni configuraciones fuera de esto.
"Ally asignado" = orders.ally_id == current.id; si no → 403. Admin siempre permitido.

────────────────────────────────────────────────────────────────────

1. [URGENTE · seguridad] GET /pets/{id} sin autenticación
   modules/pets/api/router.py:98 no depende de get_current_user: cualquiera con el UUID
   lee la mascota. Exigir auth y permitir solo: dueño, ally asignado a una orden de esa
   mascota (orders_repo.is_ally_assigned_to_pet ya existe) o admin.

────────────────────────────────────────────────────────────────────

2. Datos de la parada en las asignaciones del ally
   a) GET /orders/my-assignments — agregar query param opcional:
   date=YYYY-MM-DD (zona America/Lima, filtra por scheduled_at)
   Orden de la respuesta: scheduled_at ASC (es el orden de ruta definido por el admin).
   b) NUEVO GET /orders/my-assignments/{id} — ally asignado. Hoy no existe y el front
   lista todas las órdenes y filtra localmente.
   c) Agregar en la respuesta de (a) y (b), solo para rol ally:
   pet: { id, name, species, breed_name, sex, birth_date, weight_kg,
   photo_url (signed read URL), notes, skin_sensitivity, bath_behavior,
   tolerates_drying, tolerates_nail_clipping, special_shampoo }
   client: { first_name, last_name, phone } # users.phone ya existe
   service: { name, addons: [{ id, name }] } # resolver meta.addon_ids a nombres
   Nada de esto es campo nuevo en BD: son joins sobre lo que ya existe.

────────────────────────────────────────────────────────────────────

3. Proceso fijo del servicio (paso a paso con "Siguiente") + adicionales realizados

3a. Pasos fijos

- Nuevo campo orders.service_step (string, nullable) + migración Alembic.
  Lista FIJA en código (constante, sin tabla ni configuración), igual para
  todos los servicios:
  reception → Recepción y recojo (foto inicial + pesaje)
  bath → Baño
  drying → Secado
  finishing → Corte y acabado
  return → Devolución al domicilio
- POST /orders/{id}/arrive (ya existe) → además setea service_step="reception".
- NUEVO POST /orders/{id}/next-step (ally asignado; status=in_service)
  body: { from_step: "<paso actual>" } # evita doble avance por doble tap/reintento
  → avanza al siguiente paso de la lista; 409 si from_step != service_step
  o si ya está en "return" (el último paso se cierra con /complete).
  → desde "reception": 409 si no existe foto kind="initial" (pedido 6).
  → desde "finishing": 409 si algún addon comprado no está en addons_done (3b).
  → registra timestamp del paso y notifica al cliente
  (reusar \_notify de transitions.py; data: {order_id, status, service_step}).
  → responde OrderOut.
- POST /orders/{id}/complete (ya existe) → exigir service_step="return" (409 si no).
- Corregir el texto de la notificación de arrive en \_STATUS_LABELS: hoy dice
  "¡El grooming comenzó!"; con el modelo van debe decir que el groomer llegó
  para recoger a la mascota.

3b. Adicionales realizados
Los addons comprados (desparasitación, baño medicado, etc.) NO son pasos de la
secuencia: el groomer los marca como realizados en cualquier momento del grooming,
y todos deben estar marcados antes de pasar a "return".

- Nuevo campo orders.addons_done: [{ addon_id, done_at }] (JSON) + migración.
- NUEVO POST /orders/{id}/addons/{addon_id}/done (ally asignado;
  status=in_service y service_step en bath | drying | finishing)
  → 404 si addon_id no está en los addons comprados de la orden
  (items_snapshot[].meta.addon_ids).
  → idempotente: si ya estaba marcado, responde 200 sin duplicar ni renotificar.
  → notifica al cliente "<nombre del addon> realizado"
  (data: {order_id, addon_id}).
  → responde OrderOut.

- Agregar a OrderOut:
  service_step: string | null
  service_steps_log: [{ step, started_at }]
  addons_done: [{ addon_id, done_at }]

────────────────────────────────────────────────────────────────────

4. Saltar parada (mascota/tutor no encontrados)

- NUEVO POST /orders/{id}/skip (ally asignado; status on_the_way, o in_service
  con service_step="reception")
  body: { reason: "pet_not_present" | "tutor_not_present" | "other",
  note?: string }
  → nuevo valor OrderStatus.skipped; guarda skip_reason, skip_note, skipped_at.
  → la orden sale de la ruta activa del ally (sigue apareciendo en
  my-assignments con status=skipped).
  → notifica al cliente y a todos los usuarios con rol admin.
  → detiene el tracking de esa orden (como en done).
- POST /admin/orders/{id}/assign (ya existe) sobre una orden skipped → la regresa
  a status=created, limpia service_step y addons_done, y la reprograma con el
  nuevo scheduled_at.
- Admin: GET /admin/orders?status=skipped ya funciona con el enum nuevo.
  ⚠ paku-user debe reconocer el estado "skipped" (lo cubre el front).

────────────────────────────────────────────────────────────────────

5. Reporte de tráfico / demora

- NUEVO POST /orders/{id}/delay-report (ally asignado; status accepted u on_the_way)
  body: { delay_minutes: int (1–180), note?: string }
  → guarda el evento (order_id, ally_id, delay_minutes, note, created_at).
  → notificación al cliente ("Tu groomer llegará ~X min más tarde") y a todos
  los usuarios con rol admin.
- GET /orders/{id}/delay-reports (ally asignado, cliente dueño, admin).

────────────────────────────────────────────────────────────────────

6. Fotos del servicio tomadas por el groomer
   Hoy /media/signed-upload solo deja subir fotos de mascota a su dueño.

- /media/signed-upload y confirm: nuevo entity_type="order"
  (GCS: orders/{order_id}/...). Subida: ally asignado o admin.
  Lectura (/media/signed-read): además el cliente dueño.
- NUEVO POST /orders/{id}/photos (ally asignado)
  body: { object_name, kind: "initial" | "final" | "incident", note?: string }
- NUEVO GET /orders/{id}/photos (ally asignado, cliente dueño, admin)
  → [{ id, kind, read_url, note, created_at }]
  Uso: "initial" en recepción (obligatoria para avanzar desde reception),
  "final" antes de devolver, "incident" desde "Registrar incidencia/foto".

────────────────────────────────────────────────────────────────────

7. Configuración (no es desarrollo)

- Confirmar que GOOGLE_ROUTES_API_KEY está configurada en el entorno: el mapa del
  groomer usa GET /tracking/orders/{id}/route (ya existe; hoy responde 501 sin key).
- Login del groomer: correo + contraseña por POST /auth/login (ya existe, sin cambios).
- Cámara en vivo: se usa la del teléfono del groomer con el streaming actual
  (sin cambios).

────────────────────────────────────────────────────────────────────
Prioridad sugerida: 1 → 2 → 3 → 6 → 4 → 5
