# Pendientes

Temas identificados que no se resuelven en la etapa actual. "Por decidir" requiere una decisión
del dueño; "Para después" ya está entendido y se programa más adelante.

## Por decidir

- **Un carrito, ¿una sola orden?** Hoy un carrito `checked_out` permite crear varias órdenes con
  `POST /orders` (el carrito no queda marcado como usado). Decidir si un carrito genera una sola orden.
- ~~**Reserva por día ↔ orden.**~~ Resuelto el 2026-10-04 (C-15): reserva antes de comprar, vence con
  el carrito, se confirma con la orden y se libera al cancelar/saltar.
- **Órdenes sin pagar que ocupan cupo.** Una orden creada y nunca pagada mantiene su reserva confirmada.
  Decidir si una orden impaga se cancela sola después de cierto tiempo (y libera el cupo).

## Antes de pasar a producción

- **paku-user es app de tienda** (respuesta del front, 2026-10-05): los teléfonos con versión vieja no
  entenderán el renombre `ally` → `groomer` (C-09) ni la reserva obligatoria en el carrito (C-15). Al
  desplegar en producción, forzar la actualización de la app (versión mínima) o coordinar una ventana.

## Configuración del servidor (no es código)

- **`PUSH_PROVIDER=expo`** en el `.env` del servidor de pruebas para que los push salgan de verdad (C-18).
- **Verificar `api.paku.com.pe/health`** (2026-10-05): responde `{"app": "tms-backend", "environment":
  "development"}`. El nombre por defecto del backend de Paku es "Paku Backend": o `APP_NAME` está mal
  configurado en el servidor, o esa URL apunta a otro servicio. Confirmarlo con quien despliega.

- **`GOOGLE_ROUTES_API_KEY`** (pedido 7) — análisis del 2026-10-03, se retoma más adelante:
  - **Quién la usa:** solo `GET /tracking/orders/{id}/route` (`app/modules/tracking/use_cases/get_route.py`).
    Sin la clave responde 501; con ella llama a Google Routes (`computeRoutes`) y devuelve
    `eta_seconds`, `eta_display`, `distance_meters` y `polyline`.
  - **Sin ella funciona** `GET /tracking/orders/{id}/current` (posición del groomer + destino, sin Google)
    y todo el resto del backend.
  - **¿Necesaria?** Solo si el mapa muestra ruta dibujada y tiempo de llegada. El pedido 7 del front dice
    que el mapa del groomer usa `/route`.
  - **Dónde va:** en el `.env` del servidor. El backend no lee `.env.example` (solo `.env.local` y `.env`);
    hoy la clave está solo en `.env.example`, así que no se está usando. El dueño decidió mantener esa
    clave (repo privado).
  - **Costo:** cada llamada a `/route` es una consulta pagada a Google y no hay caché. Recomendar al front
    llamar `/route` cada 30–60 s y usar `/current` para mover el punto; o agregar caché en el backend.
  - Para habilitarla: proyecto GCP de Paku con facturación → habilitar "Routes API" → la clave restringida
    a Routes API y a la IP del servidor → `.env` del servidor → `docker compose up -d`.
- **Migraciones nuevas** `1a2b3c4d5e6f` → `2b3c4d5e6f7a` → `3c4d5e6f7a8b`: corren solas al arrancar el
  contenedor (`alembic upgrade head`). Probarlas antes en una copia de la BD.
- **Venv local** sin `firebase_admin` ni `PyJWT` (están en `requirements.txt`): `pip install -r requirements.txt`.
- **Tests de integración** (`tests/*.py`, necesitan Postgres) estaban desactualizados antes de este
  trabajo (usan el estado `in_process`, ítems `kind=product`, etc.). Los unitarios (`tests/unit`) están al día.

## Para después

- **Refresh token.** `POST /auth/refresh` emite un access token desde los datos del refresh token
  (30 días) sin consultar la BD: rol y estado activo pueden quedar desactualizados hasta 30 días y
  `profile_completed` se fuerza a `true` (se salta `require_profile_complete`). No hay rotación ni
  revocación. Además, la mayoría de endpoints confía en los datos del token en lugar de la BD, así que
  un usuario desactivado sigue entrando mientras su token sea válido.
- **Streaming.** Secretos y credenciales TURN con valores por defecto en `settings.py`; revisar
  junto con la configuración de producción.
- **Reset de contraseña.** El token se escribe en logs (nivel WARNING), puede reusarse durante
  15 minutos y no hay envío de correo.
- **Configuración por defecto insegura.** `SECRET_KEY` con valor por defecto, `DEBUG=true` por
  defecto (además vuelca SQL a los logs), CORS `*` por defecto. Verificar las variables de producción.
- **Transacciones.** Cada método de repositorio hace su propio commit; operaciones de varios pasos no
  son atómicas (ej. crear la orden y luego `order_pets`).
- **Rate limit de login en memoria por IP.** Detrás de nginx probablemente todos los clientes
  comparten IP (no verificado).
- **Integración con HCVet (etapa 2).** Ver `plan-de-trabajo.md`.
